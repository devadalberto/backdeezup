"""
Extract images and videos from downloaded .eml files into GmailAttachment records.

Parses raw .eml files already on disk, pulls out image/* and video/* MIME parts,
saves them to disk, and populates GmailAttachment with local_path + sha256.

Filters to family/personal senders by default — pass --all to extract everything.

Usage:
    # Family + personal only (default)
    docker compose exec web python manage.py extract_attachments

    # All messages with attachments
    docker compose exec web python manage.py extract_attachments --all

    # Limit for testing
    docker compose exec web python manage.py extract_attachments --limit 100

    # Dry-run (count only, no files written)
    docker compose exec web python manage.py extract_attachments --dry-run
"""
import email
import email.policy
import hashlib
import os
import re
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

# Addresses tagged as personal / family — attachments from these are priority
# Identity groups — tag names used to categorise attachments
IDENTITY_GROUPS = {
    "adalberto": [
        "jose.valdes@gmail.com",
        "josevaldesales@gmail.com",
        "valdes.sacv@gmail.com",
        "jose@vertexchaos.com",
        "jose.valdes@daimlertruck.com",
        "javalace@agentmail.to",
        "javalace@hotmail.com",
        "javaldes.bocar@gmail.com",
        "senalamientos@gmail.com",
        "jose@valher.net",
        "wii@valher.net",
    ],
    "monica": [
        "mony.bello@gmail.com",
    ],
    "little-owls": [
        "monica_littleowls@outlook.com",
    ],
    "emiliano": [
        "virlochov@gmail.com",
    ],
    "julieta": [
        "julietvlhr@gmail.com",
    ],
}

# Flat list for filtering
FAMILY_ADDRESSES = [addr for addrs in IDENTITY_GROUPS.values() for addr in addrs]

IMAGE_MIMES = {
    "image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp",
    "image/heic", "image/heif", "image/tiff", "image/bmp", "image/svg+xml",
}
VIDEO_MIMES = {
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
    "video/webm", "video/mpeg", "video/3gpp", "video/x-flv", "video/avi",
}
TARGET_MIMES = IMAGE_MIMES | VIDEO_MIMES


def _safe_filename(name: str) -> str:
    """Strip path traversal and dangerous chars from attachment filename."""
    name = os.path.basename(name or "attachment")
    name = re.sub(r'[^\w.\-]', '_', name)
    return name[:200] or "attachment"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _attachment_dir(account_email: str, year: str, month: str, gmail_id: str) -> str:
    safe_email = account_email.replace("@", "_at_").replace(".", "_")
    base = os.path.join(settings.MEDIA_ROOT, "gmail", "attachments",
                        safe_email, year, month, gmail_id)
    os.makedirs(base, exist_ok=True)
    return base


def _parse_eml(raw_path: str):
    """
    Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples
    for every image or video part found.
    attachment_id is derived from part index since .eml files don't have Gmail IDs.
    """
    with open(raw_path, "rb") as f:
        msg = email.message_from_bytes(f.read(), policy=email.policy.compat32)

    for i, part in enumerate(msg.walk()):
        ct = part.get_content_type().lower()
        if ct not in TARGET_MIMES:
            continue

        disp = str(part.get("Content-Disposition", ""))
        filename = part.get_filename() or ""

        # Skip inline images that are tiny tracking pixels (< 1KB)
        payload = part.get_payload(decode=True)
        if not payload or len(payload) < 512:
            continue

        filename = _safe_filename(filename) if filename else f"attachment_{i}.{ct.split('/')[-1]}"
        att_id = f"eml_part_{i}"

        yield att_id, filename, ct, payload


class Command(BaseCommand):
    help = "Extract images/videos from .eml files into GmailAttachment records"

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true",
                            help="Extract from all messages (default: family/personal only)")
        parser.add_argument("--limit", type=int, default=0,
                            help="Max messages to process (0 = all)")
        parser.add_argument("--dry-run", action="store_true",
                            help="Count only — no files written, no DB changes")
        parser.add_argument("--workers", type=int, default=8,
                            help="Concurrent workers (default: 8)")
        parser.add_argument("--reimport", action="store_true",
                            help="Re-extract even if GmailAttachment records already exist")

    def handle(self, *args, **options):
        from google_gmail_backup.models import GmailMessage, GmailAttachment
        from django.db.models import Q

        extract_all = options["all"]
        limit = options["limit"]
        dry_run = options["dry_run"]
        workers = options["workers"]
        reimport = options["reimport"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no files written"))

        # Build queryset
        qs = GmailMessage.objects.filter(
            state=GmailMessage.STATE_VERIFIED,
            raw_path__isnull=False,
        ).exclude(raw_path="")

        if not extract_all:
            q = Q()
            for addr in FAMILY_ADDRESSES:
                q |= Q(from_address__icontains=addr)
            qs = qs.filter(q)
            self.stdout.write(f"Filtering to {len(FAMILY_ADDRESSES)} family/personal addresses")

        if not reimport:
            # Skip messages already fully processed
            already_done = set(
                GmailAttachment.objects.filter(local_path__isnull=False)
                .values_list("message_id", flat=True).distinct()
            )
            qs = qs.exclude(id__in=already_done)

        qs = list(qs.order_by("date"))
        if limit:
            qs = qs[:limit]

        total = len(qs)
        if total == 0:
            self.stdout.write("No messages to process.")
            return

        self.stdout.write(f"Processing {total} messages with {workers} workers...")

        counters = {"msgs": 0, "extracted": 0, "skipped": 0, "errors": 0}
        lock = threading.Lock()
        start = time.time()
        REPORT_EVERY = max(1, total // 20)

        def _process(msg):
            from google_gmail_backup.models import GmailAttachment
            from django import db
            db.close_old_connections()

            if not msg.raw_path or not os.path.exists(msg.raw_path):
                return 0, 0, 1  # extracted, skipped, errors

            extracted = skipped = errors = 0
            try:
                parts = list(_parse_eml(msg.raw_path))
                if not parts:
                    return 0, 1, 0

                if dry_run:
                    return len(parts), 0, 0

                # Derive year/month from message date or file mtime
                if msg.date:
                    year = str(msg.date.year)
                    month = f"{msg.date.month:02d}"
                else:
                    mtime = os.path.getmtime(msg.raw_path)
                    from datetime import datetime
                    dt = datetime.fromtimestamp(mtime)
                    year, month = str(dt.year), f"{dt.month:02d}"

                att_dir = _attachment_dir(msg.account_email, year, month, msg.gmail_id)

                for att_id, filename, mime_type, data in parts:
                    # Deduplicate by sha256 within this message
                    sha = _sha256(data)

                    # Build unique path — avoid overwriting if same filename
                    dest = os.path.join(att_dir, filename)
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(filename)
                        dest = os.path.join(att_dir, f"{base}_{sha[:8]}{ext}")

                    with open(dest, "wb") as f:
                        f.write(data)

                    GmailAttachment.objects.update_or_create(
                        message=msg,
                        attachment_id=att_id,
                        defaults={
                            "filename": filename,
                            "mime_type": mime_type,
                            "size": len(data),
                            "sha256": sha,
                            "local_path": dest,
                            "downloaded_at": timezone.now(),
                        },
                    )
                    extracted += 1

            except Exception as exc:
                errors += 1
                msg.error = f"extract_attachments: {exc}"
                msg.save(update_fields=["error"])
            finally:
                db.close_old_connections()

            return extracted, skipped, errors

        def _print_progress():
            elapsed = time.time() - start
            n = counters["msgs"]
            rate = n / elapsed if elapsed > 0 else 0
            pct = n / total * 100
            bar = "=" * int(pct / 5) + "-" * (20 - int(pct / 5))
            eta = (total - n) / rate if rate > 0 else 0
            self.stderr.write(
                f"\r  [{bar}] {pct:5.1f}%  {n}/{total}  {rate:.1f} msg/s  "
                f"ETA {int(eta//60):02d}:{int(eta%60):02d}  "
                f"extracted={counters['extracted']} err={counters['errors']}          "
            )
            self.stderr.flush()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process, msg): msg for msg in qs}
            for future in as_completed(futures):
                ex, sk, er = future.result()
                with lock:
                    counters["msgs"] += 1
                    counters["extracted"] += ex
                    counters["skipped"] += sk
                    counters["errors"] += er
                    if counters["msgs"] % REPORT_EVERY == 0 or counters["msgs"] == total:
                        _print_progress()

        self.stderr.write("\n")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {counters['extracted']} attachments extracted "
            f"from {counters['msgs']} messages "
            f"({counters['skipped']} no attachments, {counters['errors']} errors)"
        ))

        # Summary by type
        if not dry_run and counters["extracted"] > 0:
            from google_gmail_backup.models import GmailAttachment
            from django.db.models import Count
            self.stdout.write("\nBy MIME type:")
            for row in (GmailAttachment.objects
                        .filter(local_path__isnull=False)
                        .values("mime_type")
                        .annotate(n=Count("id"))
                        .order_by("-n")):
                self.stdout.write(f"  {row['mime_type']:40s} {row['n']}")
