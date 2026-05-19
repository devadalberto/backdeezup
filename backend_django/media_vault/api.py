"""
Media Vault API — progress, decisions, import status, import trigger.
Mounted at /api/vault/ in config/urls.py.
"""
from ninja import NinjaAPI

from .models import MediaDecision, VaultImage, VaultMedia

from ninja.security import django_auth

vault_api = NinjaAPI(urls_namespace="vault", docs_url="/docs", auth=django_auth)


@vault_api.get("/status")
def vault_status(request):
    """Overview of vault contents and review progress."""
    images_total = VaultImage.objects.count()
    images_keep = VaultImage.objects.filter(keep=True).count()
    images_delete = VaultImage.objects.filter(keep=False).count()
    images_undecided = VaultImage.objects.filter(keep__isnull=True).count()

    media_total = VaultMedia.objects.count()
    media_keep = VaultMedia.objects.filter(keep=True).count()
    media_delete = VaultMedia.objects.filter(keep=False).count()
    media_undecided = VaultMedia.objects.filter(keep__isnull=True).count()

    decisions_total = MediaDecision.objects.count()

    return {
        "images": {
            "total": images_total, "keep": images_keep,
            "delete": images_delete, "undecided": images_undecided,
            "reviewed_pct": round((images_keep + images_delete) / max(images_total, 1) * 100, 1),
        },
        "media": {
            "total": media_total, "keep": media_keep,
            "delete": media_delete, "undecided": media_undecided,
            "reviewed_pct": round((media_keep + media_delete) / max(media_total, 1) * 100, 1),
        },
        "decisions_logged": decisions_total,
        "total_items": images_total + media_total,
        "total_undecided": images_undecided + media_undecided,
    }


@vault_api.post("/decide")
def record_decision(request):
    """Record a keep/delete/undecided decision for a vault item."""
    from pydantic import ValidationError
    from schemas import MediaDecisionPayload
    try:
        payload = MediaDecisionPayload.model_validate_json(request.body)
    except ValidationError as exc:
        return {"error": "Validation failed", "details": exc.errors()}

    keep_value = True if payload.action == "keep" else (False if payload.action == "delete" else None)

    if payload.item_type == "image":
        VaultImage.objects.filter(id=payload.item_id).update(keep=keep_value)
    elif payload.item_type == "video":
        VaultMedia.objects.filter(id=payload.item_id).update(keep=keep_value)

    MediaDecision.objects.create(
        item_type=payload.item_type,
        item_id=payload.item_id,
        action=payload.action,
        decided_by=request.user.username if request.user.is_authenticated else "anonymous",
    )

    return {"recorded": True, "item_type": payload.item_type, "item_id": payload.item_id, "action": payload.action}


@vault_api.get("/next-undecided")
def next_undecided(request, item_type: str = "image"):
    """Returns the next undecided item for the review UI."""
    if item_type == "image":
        item = VaultImage.objects.filter(keep__isnull=True).order_by("id").first()
        if not item:
            return {"done": True}
        return {
            "done": False, "id": item.id, "title": item.title,
            "url": item.file.url if item.file else None,
            "source_type": item.source_type, "source_id": item.source_id, "type": "image",
        }
    item = VaultMedia.objects.filter(keep__isnull=True, type="video").order_by("id").first()
    if not item:
        return {"done": True}
    sources = [{"src": s["src"], "type": s["type"]} for s in item.sources] if hasattr(item, "sources") else []
    return {
        "done": False, "id": item.id, "title": item.title,
        "sources": sources, "source_type": item.source_type, "type": "video",
    }


@vault_api.get("/image-full/{image_id}")
def image_full_url(request, image_id: int):
    """Return full-size URL for image lightbox."""
    item = VaultImage.objects.filter(id=image_id).first()
    if not item:
        return {"url": None, "error": "not found"}
    rendition = item.get_rendition("max-1200x1200")
    return {"url": rendition.url, "width": rendition.width, "height": rendition.height}


@vault_api.post("/import")
def trigger_import(request, source: str = "all", limit: int = 0, dry_run: bool = False):
    """
    Run the import_media pipeline inline — scan Drive/Gmail backups → VaultImage/VaultMedia.
    source: drive | gmail | all
    limit: max items per source (0 = unlimited)
    dry_run: if true, count only — no files written
    """
    import mimetypes
    import os
    from django.core.files import File
    from django.db import transaction

    IMAGE_MIMES = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "image/heic", "image/heif", "image/tiff", "image/bmp", "image/svg+xml",
    }
    VIDEO_MIMES = {
        "video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska",
        "video/webm", "video/mpeg", "video/3gpp", "video/x-flv",
    }
    AUDIO_MIMES = {
        "audio/mpeg", "audio/mp4", "audio/wav", "audio/ogg",
        "audio/flac", "audio/aac", "audio/x-m4a",
    }

    def guess_mime(path, fallback=""):
        m, _ = mimetypes.guess_type(path)
        return m or fallback

    imported_images = imported_media = skipped = errors = 0

    if source in ("drive", "all"):
        from google_media_backup.models import DriveAsset
        qs = DriveAsset.objects.filter(
            state="VERIFIED", download_path__isnull=False
        ).exclude(download_path="").order_by("id")
        if limit:
            qs = qs[:limit]
        for asset in qs:
            if not asset.download_path or not os.path.exists(asset.download_path):
                skipped += 1
                continue
            mime = guess_mime(asset.download_path, asset.mime_type)
            if mime in IMAGE_MIMES:
                if VaultImage.objects.filter(source_id=asset.drive_id, source_type="drive").exists():
                    skipped += 1; continue
                if dry_run:
                    imported_images += 1; continue
                try:
                    with transaction.atomic():
                        with open(asset.download_path, "rb") as f:
                            img = VaultImage(title=asset.name[:255], source_type="drive",
                                             source_id=asset.drive_id, source_email="")
                            img.file.save(os.path.basename(asset.download_path), File(f), save=False)
                            img.save()
                    imported_images += 1
                except Exception:
                    errors += 1
            elif mime in VIDEO_MIMES | AUDIO_MIMES:
                if VaultMedia.objects.filter(source_id=asset.drive_id, source_type="drive").exists():
                    skipped += 1; continue
                media_type = "video" if mime in VIDEO_MIMES else "audio"
                if dry_run:
                    imported_media += 1; continue
                try:
                    with transaction.atomic():
                        with open(asset.download_path, "rb") as f:
                            vm = VaultMedia(title=asset.name[:255], type=media_type,
                                            source_type="drive", source_id=asset.drive_id)
                            vm.file.save(os.path.basename(asset.download_path), File(f), save=False)
                            vm.save()
                    imported_media += 1
                except Exception:
                    errors += 1
            else:
                skipped += 1

    if source in ("gmail", "all"):
        from google_gmail_backup.models import GmailAttachment
        qs = GmailAttachment.objects.filter(
            local_path__isnull=False
        ).exclude(local_path="").order_by("id")
        if limit:
            qs = qs[:limit]
        for att in qs:
            if not att.local_path or not os.path.exists(att.local_path):
                skipped += 1; continue
            mime = guess_mime(att.local_path, att.mime_type)
            source_id = f"gmail_att_{att.id}"
            if mime in IMAGE_MIMES:
                if VaultImage.objects.filter(source_id=source_id, source_type="gmail").exists():
                    skipped += 1; continue
                if dry_run:
                    imported_images += 1; continue
                try:
                    with transaction.atomic():
                        with open(att.local_path, "rb") as f:
                            img = VaultImage(
                                title=att.filename[:255] or f"Gmail attachment {att.id}",
                                source_type="gmail", source_id=source_id,
                                source_email=att.message.account_email)
                            img.file.save(os.path.basename(att.local_path), File(f), save=False)
                            img.save()
                    imported_images += 1
                except Exception:
                    errors += 1
            elif mime in VIDEO_MIMES | AUDIO_MIMES:
                if VaultMedia.objects.filter(source_id=source_id, source_type="gmail").exists():
                    skipped += 1; continue
                media_type = "video" if mime in VIDEO_MIMES else "audio"
                if dry_run:
                    imported_media += 1; continue
                try:
                    with transaction.atomic():
                        with open(att.local_path, "rb") as f:
                            vm = VaultMedia(
                                title=att.filename[:255] or f"Gmail media {att.id}",
                                type=media_type, source_type="gmail", source_id=source_id,
                                source_email=att.message.account_email)
                            vm.file.save(os.path.basename(att.local_path), File(f), save=False)
                            vm.save()
                    imported_media += 1
                except Exception:
                    errors += 1
            else:
                skipped += 1

    return {
        "dry_run": dry_run,
        "source": source,
        "imported_images": imported_images,
        "imported_media": imported_media,
        "skipped": skipped,
        "errors": errors,
        "total_vault_images": VaultImage.objects.count(),
        "total_vault_media": VaultMedia.objects.count(),
    }
