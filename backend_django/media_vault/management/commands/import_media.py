"""
Import pipeline: scan backed-up Drive/Gmail media → populate VaultImage/VaultMedia.

Reads existing DriveAsset (VERIFIED state) and GmailAttachment records,
opens the local file on disk, and creates VaultImage or VaultMedia entries
so everything appears in the Wagtail CMS without manual upload.

Usage:
    make import-media              # import all
    make import-media ARGS="--limit 100"
    make import-media ARGS="--source drive"
    make import-media ARGS="--source gmail"
    make import-media ARGS="--dry-run"

Safe to run multiple times — skips files already imported (by source_id).
"""
import mimetypes
import os

from django.core.management.base import BaseCommand
from django.core.files import File
from django.db import transaction


IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "image/heic", "image/heif", "image/tiff", "image/bmp",
    "image/svg+xml",
}
VIDEO_MIMES = {
    "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
    "video/webm", "video/mpeg", "video/3gpp", "video/x-flv",
}
AUDIO_MIMES = {
    "audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg",
    "audio/flac", "audio/aac", "audio/x-m4a",
}


def _guess_mime(path: str, fallback: str = "") -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or fallback


class Command(BaseCommand):
    help = "Import backed-up Drive/Gmail media into the Wagtail Media Vault (idempotent)"

    def add_arguments(self, parser):
        parser.add_argument("--source", choices=["drive", "gmail", "all"], default="all")
        parser.add_argument("--limit", type=int, default=0, help="Max items per source (0=all)")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be imported without writing")

    def handle(self, *args, **options):
        source = options["source"]
        limit = options["limit"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no files will be written"))

        imported_images = imported_media = skipped = errors = 0

        if source in ("drive", "all"):
            i, m, s, e = self._import_drive(limit, dry_run)
            imported_images += i; imported_media += m; skipped += s; errors += e

        if source in ("gmail", "all"):
            i, m, s, e = self._import_gmail(limit, dry_run)
            imported_images += i; imported_media += m; skipped += s; errors += e

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. images={imported_images} videos/audio={imported_media} "
            f"skipped={skipped} errors={errors}"
        ))

    def _import_drive(self, limit, dry_run):
        from google_media_backup.models import DriveAsset
        from media_vault.models import VaultImage, VaultMedia

        qs = DriveAsset.objects.filter(
            state="VERIFIED",
            download_path__isnull=False,
        ).exclude(download_path="").order_by("imported_at")

        if limit:
            qs = qs[:limit]

        images = media_items = skipped = errors = 0

        for asset in qs:
            if not asset.download_path or not os.path.exists(asset.download_path):
                self.stdout.write(f"  SKIP (file missing): {asset.name}")
                skipped += 1
                continue

            mime = _guess_mime(asset.download_path, asset.mime_type)

            if mime in IMAGE_MIMES:
                if VaultImage.objects.filter(source_id=asset.drive_id, source_type="drive").exists():
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(f"  [DRY] image: {asset.name} ({mime})")
                    images += 1
                    continue
                try:
                    with transaction.atomic():
                        with open(asset.download_path, "rb") as f:
                            img = VaultImage(
                                title=asset.name[:255],
                                source_type="drive",
                                source_id=asset.drive_id,
                                source_email="",
                            )
                            img.file.save(os.path.basename(asset.download_path), File(f), save=False)
                            img.save()
                    images += 1
                    self.stdout.write(f"  image: {asset.name}")
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  ERROR image {asset.name}: {exc}"))
                    errors += 1

            elif mime in VIDEO_MIMES | AUDIO_MIMES:
                if VaultMedia.objects.filter(source_id=asset.drive_id, source_type="drive").exists():
                    skipped += 1
                    continue
                media_type = "video" if mime in VIDEO_MIMES else "audio"
                if dry_run:
                    self.stdout.write(f"  [DRY] {media_type}: {asset.name} ({mime})")
                    media_items += 1
                    continue
                try:
                    with transaction.atomic():
                        with open(asset.download_path, "rb") as f:
                            vm = VaultMedia(
                                title=asset.name[:255],
                                type=media_type,
                                source_type="drive",
                                source_id=asset.drive_id,
                            )
                            vm.file.save(os.path.basename(asset.download_path), File(f), save=False)
                            vm.save()
                    media_items += 1
                    self.stdout.write(f"  {media_type}: {asset.name}")
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  ERROR media {asset.name}: {exc}"))
                    errors += 1
            else:
                skipped += 1

        return images, media_items, skipped, errors

    def _import_gmail(self, limit, dry_run):
        from google_gmail_backup.models import GmailAttachment
        from media_vault.models import VaultImage, VaultMedia

        qs = GmailAttachment.objects.filter(
            local_path__isnull=False,
        ).exclude(local_path="").order_by("id")

        if limit:
            qs = qs[:limit]

        images = media_items = skipped = errors = 0

        for att in qs:
            if not att.local_path or not os.path.exists(att.local_path):
                skipped += 1
                continue

            mime = _guess_mime(att.local_path, att.mime_type)
            source_id = f"gmail_att_{att.id}"

            if mime in IMAGE_MIMES:
                if VaultImage.objects.filter(source_id=source_id, source_type="gmail").exists():
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(f"  [DRY] gmail image: {att.filename} ({mime})")
                    images += 1
                    continue
                try:
                    with transaction.atomic():
                        with open(att.local_path, "rb") as f:
                            img = VaultImage(
                                title=att.filename[:255] or f"Gmail attachment {att.id}",
                                source_type="gmail",
                                source_id=source_id,
                                source_email=att.message.account_email,
                            )
                            img.file.save(os.path.basename(att.local_path), File(f), save=False)
                            img.save()
                    images += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  ERROR gmail image {att.filename}: {exc}"))
                    errors += 1

            elif mime in VIDEO_MIMES | AUDIO_MIMES:
                if VaultMedia.objects.filter(source_id=source_id, source_type="gmail").exists():
                    skipped += 1
                    continue
                media_type = "video" if mime in VIDEO_MIMES else "audio"
                if dry_run:
                    self.stdout.write(f"  [DRY] gmail {media_type}: {att.filename} ({mime})")
                    media_items += 1
                    continue
                try:
                    with transaction.atomic():
                        with open(att.local_path, "rb") as f:
                            vm = VaultMedia(
                                title=att.filename[:255] or f"Gmail media {att.id}",
                                type=media_type,
                                source_type="gmail",
                                source_id=source_id,
                                source_email=att.message.account_email,
                            )
                            vm.file.save(os.path.basename(att.local_path), File(f), save=False)
                            vm.save()
                    media_items += 1
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"  ERROR gmail media {att.filename}: {exc}"))
                    errors += 1
            else:
                skipped += 1

        return images, media_items, skipped, errors
