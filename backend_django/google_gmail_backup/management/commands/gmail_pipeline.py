"""
Gmail pipeline management command — bypasses HTTP auth entirely.
Calls service functions directly.

Usage:
    docker compose exec web python manage.py gmail_pipeline discover
    docker compose exec web python manage.py gmail_pipeline download --limit 250
    docker compose exec web python manage.py gmail_pipeline verify --limit 250
    docker compose exec web python manage.py gmail_pipeline all --limit 250
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run Gmail pipeline steps directly (bypasses HTTP auth)"

    def add_arguments(self, parser):
        parser.add_argument("step", choices=["discover", "download", "verify", "all"])
        parser.add_argument("--limit", type=int, default=250)
        parser.add_argument("--max-pages", type=int, default=20)
        parser.add_argument("--page-size", type=int, default=500)

    def handle(self, *args, **options):
        step = options["step"]
        limit = options["limit"]

        if step in ("discover", "all"):
            self._discover(options["max_pages"], options["page_size"])
        if step in ("download", "all"):
            self._download(limit)
        if step in ("verify", "all"):
            self._verify(limit)

    def _discover(self, max_pages, page_size):
        from google_gmail_backup.models import GmailMessage, GmailSyncState
        from google_gmail_backup.services_gmail import get_authenticated_email, list_message_ids
        from django.utils import timezone

        account_email = get_authenticated_email()
        if not account_email:
            self.stdout.write(self.style.ERROR("Not authenticated. Run: make auth"))
            return

        discovered = 0
        page_token = None
        pages = 0

        self.stdout.write(f"Discovering Gmail messages for {account_email}...")
        while pages < max_pages:
            ids, page_token = list_message_ids(page_token=page_token, max_results=min(page_size, 500))
            page_ids = [m["id"] for m in ids]
            existing = set(GmailMessage.objects.filter(gmail_id__in=page_ids).values_list("gmail_id", flat=True))
            new_ids = [mid for mid in page_ids if mid not in existing]
            if new_ids:
                GmailMessage.objects.bulk_create([
                    GmailMessage(gmail_id=mid, thread_id="", account_email=account_email,
                                 state=GmailMessage.STATE_DISCOVERED)
                    for mid in new_ids
                ], ignore_conflicts=True)
                discovered += len(new_ids)
            pages += 1
            if not page_token:
                break

        state, _ = GmailSyncState.objects.get_or_create(email=account_email)
        state.last_full_sync_at = timezone.now()
        state.total_messages = GmailMessage.objects.filter(account_email=account_email).count()
        state.save()
        self.stdout.write(self.style.SUCCESS(f"Discovered {discovered} new messages. Total: {state.total_messages}"))

    def _download(self, limit):
        import os
        from django.utils import timezone
        from google_gmail_backup.models import GmailMessage
        from google_gmail_backup.services_gmail import (
            get_message_metadata, get_message_raw, extract_headers,
            has_attachments, parse_date, ensure_eml_path, sha256_bytes,
        )
        from tqdm import tqdm

        qs = list(GmailMessage.objects.filter(state=GmailMessage.STATE_DISCOVERED).order_by("discovered_at")[:limit])
        if not qs:
            self.stdout.write("No messages to download.")
            return

        downloaded = errors = 0
        with tqdm(qs, desc="downloading", unit="msg", file=self.stderr, dynamic_ncols=True) as pbar:
            for msg in pbar:
                try:
                    if not msg.subject and not msg.from_address:
                        meta = get_message_metadata(msg.gmail_id)
                        if meta:
                            headers = extract_headers(meta)
                            msg.thread_id = meta.get("threadId", "")
                            msg.subject = headers["subject"]
                            msg.from_address = headers["from"]
                            msg.to_address = headers["to"]
                            msg.date = parse_date(headers["date"])
                            msg.snippet = meta.get("snippet", "")
                            msg.labels = meta.get("labelIds", [])
                            msg.size_estimate = meta.get("sizeEstimate", 0)
                            msg.has_attachments = has_attachments(meta)

                    raw = get_message_raw(msg.gmail_id)
                    if not raw:
                        msg.error = "Empty raw response"
                        msg.last_attempt_at = timezone.now()
                        msg.save(update_fields=["error", "last_attempt_at"])
                        errors += 1
                        continue

                    path = ensure_eml_path(msg.account_email, msg.date, msg.gmail_id)
                    with open(path, "wb") as f:
                        f.write(raw)

                    msg.raw_path = path
                    msg.sha256 = sha256_bytes(raw)
                    msg.downloaded_at = timezone.now()
                    msg.state = GmailMessage.STATE_DOWNLOADED
                    msg.error = None
                    msg.save(update_fields=[
                        "thread_id", "subject", "from_address", "to_address", "date",
                        "snippet", "labels", "size_estimate", "has_attachments",
                        "raw_path", "sha256", "downloaded_at", "state", "error",
                    ])
                    downloaded += 1
                    pbar.set_postfix(ok=downloaded, err=errors)
                except Exception as exc:
                    msg.error = str(exc)
                    msg.last_attempt_at = timezone.now()
                    msg.save(update_fields=["error", "last_attempt_at"])
                    errors += 1

        self.stdout.write(self.style.SUCCESS(f"Downloaded {downloaded} messages ({errors} errors)"))

    def _verify(self, limit):
        import os
        from google_gmail_backup.models import GmailMessage

        qs = list(GmailMessage.objects.filter(state=GmailMessage.STATE_DOWNLOADED).order_by("downloaded_at")[:limit])
        if not qs:
            self.stdout.write("No messages to verify.")
            return

        verified = failed = 0
        for msg in qs:
            if msg.raw_path and os.path.exists(msg.raw_path):
                msg.state = GmailMessage.STATE_VERIFIED
                msg.error = None
                msg.save(update_fields=["state", "error"])
                verified += 1
            else:
                msg.error = "Local .eml file missing"
                msg.save(update_fields=["error"])
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Verified {verified} ({failed} failed)"))
