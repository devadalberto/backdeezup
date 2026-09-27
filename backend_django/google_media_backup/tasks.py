"""
Celery tasks for Drive/Photos pipeline.
Scheduled via django_celery_beat — editable in /admin/django_celery_beat/.
"""
import logging

from celery import shared_task

from core.storage import storage_guard

log = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name="google_media_backup.tasks.task_photos_discover")
def task_photos_discover(self, max_pages=50, page_size=100):
    """Discover new Google Photos items."""
    try:
        from .models import DriveAsset
        from .services_google import list_photos_items

        discovered = 0
        token = None
        pages = 0

        while pages < max_pages:
            items, token = list_photos_items(page_size=page_size, page_token=token)
            if not items:
                break
            for it in items:
                pid = it.get("id")
                if not pid:
                    continue
                _, created = DriveAsset.objects.get_or_create(
                    drive_id=f"photos:{pid}",
                    defaults=dict(
                        name=it.get("filename", ""),
                        mime_type=it.get("mimeType", ""),
                        size_bytes=0,
                    ),
                )
                if created:
                    discovered += 1
            pages += 1
            if not token:
                break

        log.info("task_photos_discover: %d new items in %d pages", discovered, pages)
        return {"discovered": discovered, "pages": pages}
    except Exception as exc:
        log.error("task_photos_discover failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name="google_media_backup.tasks.task_photos_download_batch")
@storage_guard
def task_photos_download_batch(self, limit=50):
    """Download a batch of DISCOVERED photos."""
    import os
    try:
        from django.utils import timezone
        from .models import DriveAsset
        from .services_google import download_photos_item
        from .utils import deterministic_path

        qs = list(
            DriveAsset.objects.filter(
                state="DISCOVERED", drive_id__startswith="photos:"
            ).order_by("discovered_at")[:limit]
        )
        if not qs:
            return {"downloaded": 0, "skipped": True}

        downloaded = errors = 0
        for asset in qs:
            raw_id = asset.drive_id.removeprefix("photos:")
            kind = "video" if asset.mime_type.startswith("video/") else "image"
            hint = raw_id[:32]
            final = deterministic_path(asset.name, hint, kind=kind)
            tmp = final + ".part"
            try:
                if download_photos_item(raw_id, tmp, size_hint=asset.size_bytes) and os.path.exists(tmp):
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

        log.info("task_photos_download_batch: %d downloaded, %d errors", downloaded, errors)
        return {"downloaded": downloaded, "errors": errors}
    except Exception as exc:
        log.error("task_photos_download_batch failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(name="google_media_backup.tasks.task_drive_commit_delete")
def task_drive_commit_delete(limit=50, source="all"):
    """Commit pending deletions — trash verified assets from Google."""
    from datetime import timedelta
    from decouple import config
    from django.utils import timezone
    from .models import DriveAsset
    from .services_google import trash_or_delete

    min_days = int(config("MIN_RETENTION_DAYS", default="3"))
    mode = config("DRIVE_DELETE_MODE", default="trash")
    cutoff = timezone.now() - timedelta(days=min_days)

    qs = DriveAsset.objects.filter(state="DELETE_PENDING", discovered_at__lte=cutoff)
    if source == "photos":
        qs = qs.filter(drive_id__startswith="photos:")
    elif source == "drive":
        qs = qs.exclude(drive_id__startswith="photos:")

    assets = list(qs[:limit])
    deleted = errors = 0
    for asset in assets:
        file_id = asset.drive_id.removeprefix("photos:")
        if trash_or_delete(file_id, mode=mode):
            asset.state = "DELETED"
            asset.save(update_fields=["state"])
            deleted += 1
        else:
            errors += 1

    log.info("task_drive_commit_delete: %d deleted (mode=%s), %d errors", deleted, mode, errors)
    return {"deleted": deleted, "errors": errors, "mode": mode}


@shared_task(bind=True, max_retries=2, default_retry_delay=120,
             name="google_media_backup.tasks.task_docs_discover")
def task_docs_discover(self, max_pages=50, page_size=200):
    """Discover Drive documents (PDF, Office, Google native formats)."""
    try:
        from .models import DriveAsset
        from .services_google import list_drive_files

        discovered = 0
        token = None
        pages = 0

        while pages < max_pages:
            items, token = list_drive_files(page_size=page_size, page_token=token, media_only=False)
            if not items:
                break
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

        log.info("task_docs_discover: %d new documents in %d pages", discovered, pages)
        return {"discovered": discovered, "pages": pages}
    except Exception as exc:
        log.error("task_docs_discover failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60,
             name="google_media_backup.tasks.task_docs_download_batch")
@storage_guard
def task_docs_download_batch(self, limit=100):
    """Download a batch of DISCOVERED documents (exports Google native formats)."""
    import os
    try:
        from django.utils import timezone
        from .models import DriveAsset
        from .services_google import download_or_export_file, GOOGLE_EXPORT_MAP
        from .utils import deterministic_path

        qs = list(
            DriveAsset.objects.filter(state="DISCOVERED")
            .exclude(drive_id__startswith="photos:")
            .exclude(mime_type__startswith="image/")
            .exclude(mime_type__startswith="video/")
            .order_by("discovered_at")[:limit]
        )
        if not qs:
            return {"downloaded": 0, "skipped": True}

        downloaded = errors = 0
        for asset in qs:
            if asset.mime_type in GOOGLE_EXPORT_MAP:
                _, ext = GOOGLE_EXPORT_MAP[asset.mime_type]
            else:
                ext = os.path.splitext(asset.name)[1] or ".bin"

            hint = asset.drive_id[:32]
            final = deterministic_path(asset.name, hint, kind="document")
            if asset.mime_type in GOOGLE_EXPORT_MAP:
                base = os.path.splitext(final)[0]
                final = base + ext
            tmp = final + ".part"
            try:
                if download_or_export_file(asset.drive_id, asset.mime_type, tmp, size_hint=asset.size_bytes) and os.path.exists(tmp):
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

        log.info("task_docs_download_batch: %d downloaded, %d errors", downloaded, errors)
        return {"downloaded": downloaded, "errors": errors}
    except Exception as exc:
        log.error("task_docs_download_batch failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(name="google_media_backup.tasks.task_docs_import_vault")
def task_docs_import_vault(limit=200):
    """Import VERIFIED document DriveAssets into Wagtail VaultDocument."""
    import os
    from django.core.files import File
    from django.db import transaction
    from .models import DriveAsset
    from media_vault.models import VaultDocument

    DOC_MIMES = {
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain", "text/csv",
        "application/zip", "application/x-7z-compressed", "application/x-rar-compressed",
        "application/vnd.apple.pages", "application/vnd.apple.numbers", "application/vnd.apple.keynote",
    }

    qs = DriveAsset.objects.filter(
        state="VERIFIED",
        mime_type__in=DOC_MIMES,
    ).exclude(download_path="").order_by("discovered_at")[:limit]

    imported = skipped = errors = 0
    for asset in qs:
        if not asset.download_path or not os.path.exists(asset.download_path):
            skipped += 1
            continue
        if VaultDocument.objects.filter(source_id=asset.drive_id, source_type="drive").exists():
            skipped += 1
            continue
        try:
            with transaction.atomic():
                with open(asset.download_path, "rb") as f:
                    doc = VaultDocument(
                        title=asset.name[:255],
                        source_type="drive",
                        source_id=asset.drive_id,
                    )
                    doc.file.save(os.path.basename(asset.download_path), File(f), save=False)
                    doc.save()
            imported += 1
        except Exception as exc:
            log.error("task_docs_import_vault error on %s: %s", asset.drive_id, exc)
            errors += 1

    log.info("task_docs_import_vault: %d imported, %d skipped, %d errors", imported, skipped, errors)
    return {"imported": imported, "skipped": skipped, "errors": errors}
