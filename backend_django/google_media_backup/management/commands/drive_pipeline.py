"""
Drive/Photos pipeline management command — bypasses HTTP auth entirely.

Usage:
    docker compose exec web python manage.py drive_pipeline discover
    docker compose exec web python manage.py drive_pipeline discover-files
    docker compose exec web python manage.py drive_pipeline discover-photos
    docker compose exec web python manage.py drive_pipeline download --limit 100
    docker compose exec web python manage.py drive_pipeline verify --limit 100
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run Drive/Photos pipeline steps directly (bypasses HTTP auth)"

    def add_arguments(self, parser):
        parser.add_argument(
            "step",
            choices=["discover", "discover-files", "discover-photos", "download", "verify"],
        )
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--max-pages", type=int, default=20)
        parser.add_argument("--page-size", type=int, default=200)

    def handle(self, *args, **options):
        step = options["step"]
        if step == "discover":
            self._discover(options["max_pages"], options["page_size"], media_only=True)
        elif step == "discover-files":
            self._discover(options["max_pages"], options["page_size"], media_only=False)
        elif step == "discover-photos":
            self._discover_photos(options["max_pages"], options["page_size"])
        elif step == "download":
            self._download(options["limit"])
        elif step == "verify":
            self._verify(options["limit"])

    def _discover(self, max_pages, page_size, media_only=True):
        import uuid
        from django.utils import timezone
        from google_media_backup.models import DriveAsset, RunLog
        from google_media_backup.services_google import list_drive_files

        run = RunLog.objects.create(run_id=str(uuid.uuid4()), totals={"discovered": 0})
        discovered = 0
        token = None
        pages = 0
        label = "media" if media_only else "files"
        self.stdout.write(f"Discovering Drive {label}...")

        while pages < max_pages:
            items, token = list_drive_files(
                page_size=page_size,
                page_token=token,
                media_only=media_only,
            )
            for it in items:
                fid = it.get("id")
                if not fid:
                    continue
                _, created = DriveAsset.objects.get_or_create(
                    drive_id=fid,
                    defaults=dict(
                        name=it.get("name", ""),
                        mime_type=it.get("mimeType", ""),
                        size_bytes=int(it.get("size", 0)),
                        md5_checksum=it.get("md5Checksum", ""),
                    ),
                )
                if created:
                    discovered += 1
            pages += 1
            if not token:
                break

        run.totals["discovered"] = discovered
        run.status = "OK"
        run.finished_at = timezone.now()
        run.save()
        self.stdout.write(self.style.SUCCESS(f"Discovered {discovered} new Drive {label}."))

    def _discover_photos(self, max_pages, page_size):
        import uuid
        from django.utils import timezone
        from google_media_backup.models import DriveAsset, RunLog
        from google_media_backup.services_google import list_photos_items

        run = RunLog.objects.create(run_id=str(uuid.uuid4()), totals={"discovered": 0})
        discovered = 0
        token = None
        pages = 0
        self.stdout.write("Discovering Google Photos...")

        while pages < max_pages:
            items, token = list_photos_items(page_size=page_size, page_token=token)
            for it in items:
                pid = it.get("id")
                if not pid:
                    continue
                _, created = DriveAsset.objects.get_or_create(
                    drive_id=f"photos:{pid}",
                    defaults=dict(
                        name=it.get("filename") or pid,
                        mime_type=it.get("mimeType") or "",
                        size_bytes=0,
                        md5_checksum="",
                    ),
                )
                if created:
                    discovered += 1
            pages += 1
            if not token:
                break

        run.totals["discovered"] = discovered
        run.status = "OK"
        run.finished_at = timezone.now()
        run.save()
        self.stdout.write(self.style.SUCCESS(f"Discovered {discovered} new Photos items."))

    def _download(self, limit):
        import os
        import time
        from django.utils import timezone
        from google_media_backup.models import DriveAsset
        from google_media_backup.services_google import download_file, deterministic_path

        qs = list(DriveAsset.objects.filter(state="DISCOVERED").order_by("discovered_at")[:limit])
        if not qs:
            self.stdout.write("No assets to download.")
            return

        total = len(qs)
        downloaded = errors = 0
        start = time.time()
        REPORT_EVERY = max(1, total // 20)

        for i, asset in enumerate(qs, 1):
            kind = "image" if asset.mime_type.startswith("image/") else "video"
            hint = asset.drive_id.replace("/", "_")[:32]
            tmp = deterministic_path(asset.name, hint, kind=kind) + ".part"
            final = deterministic_path(asset.name, hint, kind=kind)
            try:
                if download_file(asset.drive_id, tmp) and os.path.exists(tmp):
                    os.replace(tmp, final)
                    asset.download_path = final
                    asset.downloaded_at = timezone.now()
                    asset.state = "DOWNLOADED"
                    asset.error = None
                    asset.save(update_fields=["download_path", "downloaded_at", "state", "error"])
                    downloaded += 1
                else:
                    asset.error = "Download failed"
                    asset.last_attempt_at = timezone.now()
                    asset.save(update_fields=["error", "last_attempt_at"])
                    errors += 1
            except Exception as exc:
                asset.error = str(exc)
                asset.last_attempt_at = timezone.now()
                asset.save(update_fields=["error", "last_attempt_at"])
                errors += 1

            if i % REPORT_EVERY == 0 or i == total:
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                pct = i / total * 100
                bar_filled = int(pct / 5)
                bar = "=" * bar_filled + "-" * (20 - bar_filled)
                eta = (total - i) / rate if rate > 0 else 0
                self.stderr.write(
                    f"\r  [{bar}] {pct:5.1f}%  {i}/{total}  "
                    f"{rate:.1f}/s  ETA {int(eta//60):02d}:{int(eta%60):02d}  "
                    f"ok={downloaded} err={errors}          "
                )
                self.stderr.flush()

        self.stderr.write("\n")
        self.stdout.write(self.style.SUCCESS(f"Downloaded {downloaded} assets ({errors} errors)"))

    def _verify(self, limit):
        import os
        from google_media_backup.models import DriveAsset, MediaItem

        qs = list(DriveAsset.objects.filter(state="DOWNLOADED").order_by("downloaded_at")[:limit])
        if not qs:
            self.stdout.write("No assets to verify.")
            return

        verified = failed = 0
        for asset in qs:
            if asset.download_path and os.path.exists(asset.download_path):
                if not asset.media_item:
                    from google_media_backup.utils import sha256_file, copy_into_media
                    sha = sha256_file(asset.download_path)
                    item, _ = MediaItem.objects.get_or_create(
                        sha256=sha,
                        defaults={"file": copy_into_media(asset.download_path, sha)},
                    )
                    asset.media_item = item
                asset.state = "VERIFIED"
                asset.error = None
                asset.save(update_fields=["media_item", "state", "error"])
                verified += 1
            else:
                asset.error = "File missing"
                asset.save(update_fields=["error"])
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Verified {verified} assets ({failed} failed)"))
