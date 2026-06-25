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
            choices=["discover", "discover-files", "discover-photos",
                     "download", "download-photos", "download-docs",
                     "verify", "mark-delete", "commit-delete"],
        )
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--max-pages", type=int, default=20)
        parser.add_argument("--page-size", type=int, default=200)
        parser.add_argument("--source", type=str, default="all",
                            help="Filter by source: all, photos, drive")

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
        elif step == "download-photos":
            self._download_photos(options["limit"])
        elif step == "download-docs":
            self._download_docs(options["limit"])
        elif step == "verify":
            self._verify(options["limit"])
        elif step == "mark-delete":
            self._mark_delete(options["limit"], options["source"])
        elif step == "commit-delete":
            self._commit_delete(options["limit"], options["source"])

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
        self.stdout.write("Discovering Google Photos items...")

        while pages < max_pages:
            items, token = list_photos_items(page_size=page_size, page_token=token)
            if not items:
                break
            for it in items:
                pid = it.get("id")
                if not pid:
                    continue
                drive_id = f"photos:{pid}"
                _, created = DriveAsset.objects.get_or_create(
                    drive_id=drive_id,
                    defaults=dict(
                        name=it.get("filename", ""),
                        mime_type=it.get("mimeType", ""),
                        size_bytes=0,
                    ),
                )
                if created:
                    discovered += 1
            pages += 1
            if pages % 5 == 0:
                self.stdout.write(f"  page {pages}: {discovered} new so far...")
            if not token:
                break

        run.totals["discovered"] = discovered
        run.status = "OK"
        run.finished_at = timezone.now()
        run.save()
        self.stdout.write(self.style.SUCCESS(f"Discovered {discovered} new Photos items."))

    def _download_photos(self, limit):
        import os
        import time
        from django.utils import timezone
        from google_media_backup.models import DriveAsset
        from google_media_backup.services_google import download_photos_item
        from google_media_backup.utils import deterministic_path

        qs = list(
            DriveAsset.objects.filter(
                state="DISCOVERED", drive_id__startswith="photos:"
            ).order_by("discovered_at")[:limit]
        )
        if not qs:
            self.stdout.write("No photos to download.")
            return

        total = len(qs)
        downloaded = errors = 0
        start = time.time()

        for i, asset in enumerate(qs, 1):
            raw_id = asset.drive_id.removeprefix("photos:")
            kind = "video" if asset.mime_type.startswith("video/") else "image"
            hint = raw_id[:32]
            final = deterministic_path(asset.name, hint, kind=kind)
            tmp = final + ".part"
            try:
                if download_photos_item(raw_id, tmp) and os.path.exists(tmp):
                    os.replace(tmp, final)
                    asset.download_path = final
                    asset.downloaded_at = timezone.now()
                    asset.state = "DOWNLOADED"
                    asset.error = ""
                    asset.save(update_fields=["download_path", "downloaded_at", "state", "error"])
                    downloaded += 1
                else:
                    asset.error = "Download failed"
                    asset.last_attempt_at = timezone.now()
                    asset.save(update_fields=["error", "last_attempt_at"])
                    errors += 1
            except Exception as exc:
                asset.error = str(exc)[:500]
                asset.last_attempt_at = timezone.now()
                asset.save(update_fields=["error", "last_attempt_at"])
                errors += 1

            if i % max(1, total // 20) == 0 or i == total:
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"  {i}/{total} ({i*100//total}%) ok={downloaded} err={errors} "
                    f"{rate:.1f}/s"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Photos download: {downloaded} ok, {errors} errors"
        ))

    def _download_docs(self, limit):
        import os
        import time
        from django.utils import timezone
        from google_media_backup.models import DriveAsset
        from google_media_backup.services_google import download_or_export_file, GOOGLE_EXPORT_MAP
        from google_media_backup.utils import deterministic_path

        qs = list(
            DriveAsset.objects.filter(state="DISCOVERED")
            .exclude(drive_id__startswith="photos:")
            .exclude(mime_type__startswith="image/")
            .exclude(mime_type__startswith="video/")
            .order_by("discovered_at")[:limit]
        )
        if not qs:
            self.stdout.write("No documents to download.")
            return

        total = len(qs)
        downloaded = errors = 0
        start = time.time()

        for i, asset in enumerate(qs, 1):
            # Determine output extension
            if asset.mime_type in GOOGLE_EXPORT_MAP:
                _, ext = GOOGLE_EXPORT_MAP[asset.mime_type]
            else:
                ext = os.path.splitext(asset.name)[1] or ".bin"

            hint = asset.drive_id[:32]
            final = deterministic_path(asset.name, hint, kind="document")
            # Override extension for Google native exports
            if asset.mime_type in GOOGLE_EXPORT_MAP:
                base = os.path.splitext(final)[0]
                final = base + ext
            tmp = final + ".part"
            try:
                if download_or_export_file(asset.drive_id, asset.mime_type, tmp) and os.path.exists(tmp):
                    os.replace(tmp, final)
                    asset.download_path = final
                    asset.downloaded_at = timezone.now()
                    asset.state = "DOWNLOADED"
                    asset.error = ""
                    asset.save(update_fields=["download_path", "downloaded_at", "state", "error"])
                    downloaded += 1
                else:
                    asset.error = "Download/export failed"
                    asset.last_attempt_at = timezone.now()
                    asset.save(update_fields=["error", "last_attempt_at"])
                    errors += 1
            except Exception as exc:
                asset.error = str(exc)[:500]
                asset.last_attempt_at = timezone.now()
                asset.save(update_fields=["error", "last_attempt_at"])
                errors += 1

            if i % max(1, total // 20) == 0 or i == total:
                elapsed = time.time() - start
                rate = i / elapsed if elapsed > 0 else 0
                self.stdout.write(
                    f"  {i}/{total} ({i*100//total}%) ok={downloaded} err={errors} "
                    f"{rate:.1f}/s"
                )

        self.stdout.write(self.style.SUCCESS(
            f"Docs download: {downloaded} ok, {errors} errors"
        ))

    def _mark_delete(self, limit, source):
        from django.utils import timezone
        from google_media_backup.models import DriveAsset

        qs = DriveAsset.objects.filter(state="VERIFIED")
        if source == "photos":
            qs = qs.filter(drive_id__startswith="photos:")
        elif source == "drive":
            qs = qs.exclude(drive_id__startswith="photos:")
        qs = qs.order_by("discovered_at")[:limit]
        count = qs.update(state="DELETE_PENDING")
        self.stdout.write(self.style.SUCCESS(f"Marked {count} assets for deletion."))

    def _commit_delete(self, limit, source):
        import os
        from datetime import timedelta
        from decouple import config
        from django.utils import timezone
        from google_media_backup.models import DriveAsset
        from google_media_backup.services_google import trash_or_delete

        min_days = int(config("MIN_RETENTION_DAYS", default="3"))
        mode = config("DRIVE_DELETE_MODE", default="trash")
        cutoff = timezone.now() - timedelta(days=min_days)

        qs = DriveAsset.objects.filter(state="DELETE_PENDING")
        if source == "photos":
            qs = qs.filter(drive_id__startswith="photos:")
        elif source == "drive":
            qs = qs.exclude(drive_id__startswith="photos:")

        assets = list(qs.filter(discovered_at__lte=cutoff)[:limit])
        if not assets:
            self.stdout.write("No assets past retention period.")
            return

        deleted = errors = 0
        for asset in assets:
            file_id = asset.drive_id
            if file_id.startswith("photos:"):
                file_id = file_id.removeprefix("photos:")
            if trash_or_delete(file_id, mode=mode):
                asset.state = "DELETED"
                asset.save(update_fields=["state"])
                deleted += 1
            else:
                asset.error = f"Delete failed (mode={mode})"
                asset.save(update_fields=["error"])
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {deleted} assets (mode={mode}), {errors} errors"
        ))

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
                    # Size integrity check: verify downloaded bytes match Drive API size
                    actual_size = os.path.getsize(tmp)
                    if asset.size_bytes > 0 and actual_size != asset.size_bytes:
                        os.unlink(tmp)
                        asset.error = f"Size mismatch: got {actual_size} expected {asset.size_bytes}"
                        asset.last_attempt_at = timezone.now()
                        asset.save(update_fields=["error", "last_attempt_at"])
                        errors += 1
                    else:
                        os.replace(tmp, final)
                        asset.download_path = final
                        asset.downloaded_at = timezone.now()
                        asset.state = "DOWNLOADED"
                        asset.error = ""
                        asset.save(update_fields=["download_path", "downloaded_at", "state", "error"])
                        downloaded += 1
                else:
                    asset.error = "Download failed"
                    asset.last_attempt_at = timezone.now()
                    asset.save(update_fields=["error", "last_attempt_at"])
                    errors += 1
            except Exception as exc:
                asset.error = str(exc)[:500]
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
                asset.error = ""
                asset.save(update_fields=["media_item", "state", "error"])
                verified += 1
            else:
                asset.error = "File missing"
                asset.save(update_fields=["error"])
                failed += 1

        self.stdout.write(self.style.SUCCESS(f"Verified {verified} assets ({failed} failed)"))
