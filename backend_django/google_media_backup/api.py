import os
import uuid
import datetime as dt
from typing import List, Optional
from ninja import NinjaAPI, Schema, Query
from django.utils import timezone
from django.conf import settings
from .models import DriveAsset, MediaItem, RunLog
from .utils import sha256_file, deterministic_path, copy_into_media
from .services_google import (
    start_oauth_local,
    list_media_files,
    list_common_files,
    list_photos_items,
    download_file,
    trash_or_delete,
)
from decouple import config

from ninja.security import django_auth

api = NinjaAPI(
    title=config('SWAGGER_TITLE', default='API'),
    description=config('SWAGGER_DESCRIPTION', default=''),
    version=config('SWAGGER_VERSION', default='0.1.0'),
    docs_url="/docs",
    auth=django_auth,
    openapi_extra={"servers": [{"url": "/"}]},
)

class AssetOut(Schema):
    id: int; drive_id: str; name: str; mime_type: str; state: str
    download_path: Optional[str] = None
    imported_at: Optional[dt.datetime] = None
    error: Optional[str] = None

class FilterIn(Schema):
    state: Optional[str] = None
    q: Optional[str] = None

@api.get("/assets", response=List[AssetOut])
def list_assets(request, filters: FilterIn = Query(...)):
    qs = DriveAsset.objects.all().order_by('-discovered_at')
    if filters.state: qs = qs.filter(state=filters.state)
    if filters.q: qs = qs.filter(name__icontains=filters.q)
    return [AssetOut(id=o.id, drive_id=o.drive_id, name=o.name, mime_type=o.mime_type,
                     state=o.state, download_path=o.download_path, imported_at=o.imported_at, error=o.error)
            for o in qs[:500]]

@api.post("/auth/connect")
def auth_connect(request):
    return {"message": start_oauth_local()}

@api.post("/sync/discover")
def sync_discover(request, page_size: int = 200, max_pages: int = 10):
    run = RunLog.objects.create(run_id=str(uuid.uuid4()), totals={"discovered": 0})
    discovered = 0
    token = None
    pages = 0
    while pages < max_pages:
        files, token = list_media_files(page_size=page_size, page_token=token)
        for f in files:
            file_id = f.get("id")
            mime = f.get("mimeType", "")
            # If it's a shortcut, use the target id/mime
            if mime == "application/vnd.google-apps.shortcut":
                tgt = f.get("shortcutDetails", {}) or {}
                file_id = tgt.get("targetId") or file_id
                mime = tgt.get("targetMimeType") or mime

            _, created = DriveAsset.objects.get_or_create(
                drive_id=file_id,
                defaults=dict(
                    name=f.get("name", ""),
                    mime_type=mime,
                    size_bytes=int(f.get("size", 0) or 0),
                    md5_checksum=f.get("md5Checksum") or "",
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
    return {"discovered": discovered, "run_id": run.run_id}


@api.post("/sync/discover-files")
def sync_discover_files(request, page_size: int = 200, max_pages: int = 10):
    """
    Discover commonly-used document types in Drive (pdf, office, csv, archives, iWork).
    """
    run = RunLog.objects.create(run_id=str(uuid.uuid4()), totals={"discovered": 0})
    discovered = 0
    token = None
    pages = 0
    while pages < max_pages:
        files, token = list_common_files(page_size=page_size, page_token=token)
        for f in files:
            _, created = DriveAsset.objects.get_or_create(
                drive_id=f["id"],
                defaults=dict(
                    name=f.get("name", ""),
                    mime_type=f.get("mimeType", ""),
                    size_bytes=int(f.get("size", 0) or 0),
                    md5_checksum=f.get("md5Checksum") or "",
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
    return {"discovered": discovered, "run_id": run.run_id}


@api.post("/sync/discover-photos")
def sync_discover_photos(request, page_size: int = 200, max_pages: int = 20):
    """
    Discover media items from Google Photos Library.
    NOTE: These are NOT Drive files; downstream download/delete will need a Photos-specific path.
    For now we prefix IDs with 'photos:' to keep DriveAsset unique.
    """
    run = RunLog.objects.create(run_id=str(uuid.uuid4()), totals={"discovered": 0})
    discovered = 0
    token = None
    pages = 0
    while pages < max_pages:
        items, token = list_photos_items(page_size=page_size, page_token=token)
        for it in items:
            pid = it.get("id")
            if not pid:
                continue
            name = it.get("filename") or it.get("id")
            mime = it.get("mimeType") or ""
            # Prefix so it doesn't collide with Drive IDs
            _, created = DriveAsset.objects.get_or_create(
                drive_id=f"photos:{pid}",
                defaults=dict(
                    name=name,
                    mime_type=mime,
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
    return {"discovered": discovered, "run_id": run.run_id}


@api.post("/sync/download")
def sync_download(request, limit: int = 20):
    qs = DriveAsset.objects.filter(state='DISCOVERED').order_by('discovered_at')[:limit]
    count = 0
    for a in qs:
        kind = 'image' if a.mime_type.startswith('image/') else 'video'
        hint = a.drive_id.replace('/','_')[:32]
        tmp = deterministic_path(a.name, hint, kind=kind) + ".part"
        final = deterministic_path(a.name, hint, kind=kind)
        if download_file(a.drive_id, tmp, size_hint=a.size_bytes) and os.path.exists(tmp):
            os.replace(tmp, final)
            a.download_path = final; a.downloaded_at = timezone.now(); a.state='DOWNLOADED'; a.error=None
            a.save(update_fields=['download_path','downloaded_at','state','error']); count += 1
        else:
            a.error="Download failed"; a.last_attempt_at=timezone.now(); a.save(update_fields=['error','last_attempt_at'])
    return {"downloaded": count}

@api.post("/sync/import")
def sync_import(request, limit: int = 20):
    qs = DriveAsset.objects.filter(state='DOWNLOADED').order_by('downloaded_at')[:limit]
    imported = 0
    for a in qs:
        if not a.download_path or not os.path.exists(a.download_path):
            a.error="Missing local file"; a.save(update_fields=['error']); continue
        digest = sha256_file(a.download_path)
        ext = (os.path.splitext(a.name)[1] or '.bin').lstrip('.').lower()
        imported_path = copy_into_media(a.download_path, digest, ext)
        rel_upload = os.path.relpath(imported_path, settings.MEDIA_ROOT)
        media, _ = MediaItem.objects.get_or_create(sha256=digest, defaults={"file": rel_upload})
        a.media_item = media; a.imported_at = timezone.now(); a.state='IMPORTED'; a.error=None
        a.save(update_fields=['media_item','imported_at','state','error']); imported += 1
    return {"imported": imported}

@api.post("/sync/verify")
def sync_verify(request, limit: int = 50):
    # select_related avoids N+1 MediaItem existence check per asset
    qs = DriveAsset.objects.filter(state='IMPORTED').select_related('media_item').order_by('imported_at')[:limit]
    verified = 0
    for a in qs:
        ok_a = bool(a.download_path and os.path.exists(a.download_path))
        ok_b = bool(a.media_item_id and a.media_item is not None)
        if ok_a and ok_b: a.state='VERIFIED'; a.error=None; verified += 1
        else: a.error="Verification failed"
        a.save(update_fields=['state','error'])
    return {"verified": verified}

@api.post("/sync/mark-delete")
def sync_mark_delete(request, limit: int = 100):
    ids = list(
        DriveAsset.objects.filter(state="VERIFIED").order_by("id").values_list("id", flat=True)[:limit]
    )
    updated = DriveAsset.objects.filter(id__in=ids).update(state="DELETE_PENDING")
    return {"queued_for_delete": updated}

@api.post("/sync/commit-delete")
def sync_commit_delete(request, force: bool = False, limit: int = 50):
    mode = 'hard' if (force or (os.getenv('DRIVE_DELETE_MODE','trash')=='hard')) else 'trash'
    min_days = int(os.getenv('MIN_RETENTION_DAYS','3')); now = timezone.now(); done = 0
    for a in DriveAsset.objects.filter(state='DELETE_PENDING')[:limit]:
        t0 = a.imported_at or a.discovered_at
        if (now - t0).days < min_days: continue
        if trash_or_delete(a.drive_id, mode=mode):
            a.state='DELETED'; a.error=None; a.save(update_fields=['state','error']); done += 1
        else:
            a.error=f"Delete failed ({mode})"; a.save(update_fields=['error'])
    return {"deleted": done, "mode": mode}


DRIVE_ASSET_FIELDS = [
    ("Drive ID", "drive_id"), ("Name", "name"), ("MIME Type", "mime_type"),
    ("Size (bytes)", "size_bytes"), ("MD5", "md5_checksum"),
    ("State", "state"), ("Download Path", "download_path"),
    ("Discovered", "discovered_at"), ("Downloaded", "downloaded_at"),
    ("Imported", "imported_at"), ("Error", "error"),
]


@api.get("/export/assets")
def export_assets(request, fmt: str = "csv", state: str = "", limit: int = 5000):
    from google_gmail_backup.exports import export_queryset
    qs = DriveAsset.objects.all().order_by("-discovered_at")
    if state:
        qs = qs.filter(state=state)
    qs = qs[:limit]
    rows = [
        {"drive_id": a.drive_id, "name": a.name, "mime_type": a.mime_type,
         "size_bytes": a.size_bytes, "md5_checksum": a.md5_checksum or "",
         "state": a.state, "download_path": a.download_path or "",
         "discovered_at": str(a.discovered_at), "downloaded_at": str(a.downloaded_at),
         "imported_at": str(a.imported_at), "error": a.error or ""}
        for a in qs
    ]
    name = f"drive_assets{'_' + state if state else ''}"
    return export_queryset(request, rows, DRIVE_ASSET_FIELDS, name, fmt)


@api.get("/progress")
def pipeline_progress(request):
    from django.db.models import Count
    counts = dict(
        DriveAsset.objects.values_list("state").annotate(n=Count("id"))
    )
    total = sum(counts.values()) or 1
    discovered  = counts.get("DISCOVERED", 0)
    downloaded  = counts.get("DOWNLOADED", 0)
    imported    = counts.get("IMPORTED", 0)
    verified    = counts.get("VERIFIED", 0)
    pending     = counts.get("DELETE_PENDING", 0)
    deleted     = counts.get("DELETED", 0)
    done        = verified + pending + deleted
    pct         = round(done / total * 100, 1)
    return {
        "total":      total,
        "discovered": discovered,
        "downloaded": downloaded,
        "imported":   imported,
        "verified":   verified,
        "pending":    pending,
        "deleted":    deleted,
        "done":       done,
        "pct":        pct,
    }
