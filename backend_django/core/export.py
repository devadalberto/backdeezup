"""Export backed-up files to ZIP/TAR (Phase 36). Read-only on stored files.

Three scopes:
- "selection": explicit gmail_ids / media_ids (used by the admin "Export selected" actions).
- "source": every backed-up item from one source ("gmail" | "media").
- "everything": every backed-up item from every source.

Only items that are actually "backed up" (per core.verification's state lists)
AND still present on disk are included -- a missing file is silently skipped,
never invented or zero-filled.

The archive is built through a small non-seekable write sink so the response
can be streamed chunk by chunk instead of held in memory: tarfile's own
streaming mode ("w|gz") is seek-free by design, and zipfile only needs
``write()``/``tell()`` (no ``seek()``) as long as members are opened with
``ZipFile.open(name, "w")``, which defers to a trailing data descriptor.
Every file's sha256 is computed while its bytes are copied into the archive
(one read pass, no separate hashing step) and recorded in a trailing
manifest.json.
"""
import hashlib
import io
import json
import os
import tarfile
import zipfile
from datetime import datetime, timezone as dt_timezone

from django.conf import settings

CHUNK_SIZE = 256 * 1024


def async_item_threshold():
    return getattr(settings, "EXPORT_ASYNC_THRESHOLD", 200)


class _StreamSink:
    """write()/tell()-only sink -- never seek()s -- so zip/tar can be built
    without ever holding the whole archive in memory."""

    def __init__(self):
        self._chunks = []
        self._pos = 0

    def write(self, data):
        self._chunks.append(data)
        self._pos += len(data)
        return len(data)

    def tell(self):
        return self._pos

    def flush(self):
        pass

    def drain(self):
        if not self._chunks:
            return b""
        data = b"".join(self._chunks)
        self._chunks = []
        return data


def _gmail_arcname(msg):
    return f"gmail/{msg.gmail_id}.eml"


def _media_arcname(asset):
    safe_name = asset.name.replace("/", "_") if asset.name else "file"
    return f"media/{asset.pk}_{safe_name}"


def resolve_export_items(scope, source=None, gmail_ids=None, media_ids=None):
    """Returns a list of dicts: kind, db_id, arcname, disk_path, size."""
    from core.verification import DRIVE_BACKED_UP_STATES, GMAIL_BACKED_UP_STATES
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    items = []

    def _add_gmail(qs):
        for msg in qs.exclude(raw_path="").order_by("id"):
            if os.path.exists(msg.raw_path):
                items.append({
                    "kind": "gmail", "db_id": msg.pk, "arcname": _gmail_arcname(msg),
                    "disk_path": msg.raw_path, "size": os.path.getsize(msg.raw_path),
                })

    def _add_media(qs):
        for asset in qs.exclude(download_path="").order_by("id"):
            if os.path.exists(asset.download_path):
                items.append({
                    "kind": "media", "db_id": asset.pk, "arcname": _media_arcname(asset),
                    "disk_path": asset.download_path, "size": os.path.getsize(asset.download_path),
                })

    if scope == "selection":
        if not gmail_ids and not media_ids:
            raise ValueError("scope=selection requires gmail_ids and/or media_ids")
        if gmail_ids:
            _add_gmail(GmailMessage.objects.filter(pk__in=gmail_ids))
        if media_ids:
            _add_media(DriveAsset.objects.filter(pk__in=media_ids))
    elif scope == "source":
        if source == "gmail":
            _add_gmail(GmailMessage.objects.filter(state__in=GMAIL_BACKED_UP_STATES))
        elif source == "media":
            _add_media(DriveAsset.objects.filter(state__in=DRIVE_BACKED_UP_STATES))
        else:
            raise ValueError("scope=source requires source=gmail|media")
    elif scope == "everything":
        _add_gmail(GmailMessage.objects.filter(state__in=GMAIL_BACKED_UP_STATES))
        _add_media(DriveAsset.objects.filter(state__in=DRIVE_BACKED_UP_STATES))
    else:
        raise ValueError(f"Unknown scope '{scope}'")
    return items


def _manifest_bytes(manifest):
    payload = {"generated_at": datetime.now(dt_timezone.utc).isoformat(), "files": manifest}
    return json.dumps(payload, indent=2).encode()


class _HashingReader:
    """Wraps a binary file so tarfile.addfile's internal copyfileobj hashes
    the bytes as they pass through, in the same read pass -- no re-read."""

    def __init__(self, fileobj, hasher):
        self._fileobj = fileobj
        self._hasher = hasher

    def read(self, n=-1):
        chunk = self._fileobj.read(n if n and n > 0 else CHUNK_SIZE)
        self._hasher.update(chunk)
        return chunk


def _add_tar_member(archive, item):
    hasher = hashlib.sha256()
    info = tarfile.TarInfo(name=item["arcname"])
    info.size = item["size"]
    info.mtime = int(datetime.now(dt_timezone.utc).timestamp())
    with open(item["disk_path"], "rb") as src:
        archive.addfile(info, _HashingReader(src, hasher))
    return hasher.hexdigest()


def _add_zip_member(archive, item):
    hasher = hashlib.sha256()
    with open(item["disk_path"], "rb") as src, archive.open(item["arcname"], "w") as dst:
        while True:
            chunk = src.read(CHUNK_SIZE)
            if not chunk:
                break
            hasher.update(chunk)
            dst.write(chunk)
    return hasher.hexdigest()


def iter_archive_stream(items, fmt):
    """Yields bytes chunks of a zip or tar.gz archive of ``items`` plus a
    trailing manifest.json. Never holds the whole archive in memory."""
    sink = _StreamSink()
    manifest = []

    if fmt == "tar":
        archive = tarfile.open(fileobj=sink, mode="w|gz")
        for item in items:
            sha = _add_tar_member(archive, item)
            manifest.append({"path": item["arcname"], "sha256": sha, "size": item["size"],
                              "kind": item["kind"], "db_id": item["db_id"]})
            data = sink.drain()
            if data:
                yield data
        manifest_bytes = _manifest_bytes(manifest)
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(manifest_bytes)
        archive.addfile(info, io.BytesIO(manifest_bytes))
        archive.close()
        data = sink.drain()
        if data:
            yield data
        return

    if fmt == "zip":
        archive = zipfile.ZipFile(sink, mode="w", compression=zipfile.ZIP_DEFLATED)
        for item in items:
            sha = _add_zip_member(archive, item)
            manifest.append({"path": item["arcname"], "sha256": sha, "size": item["size"],
                              "kind": item["kind"], "db_id": item["db_id"]})
            data = sink.drain()
            if data:
                yield data
        archive.writestr("manifest.json", _manifest_bytes(manifest))
        archive.close()
        data = sink.drain()
        if data:
            yield data
        return

    raise ValueError(f"Unknown format '{fmt}'")


def write_archive_to_file(items, fmt, dest_path):
    """Same archive, written straight to a real (seekable) file on disk --
    used by the async Celery path. Returns the manifest list."""
    manifest = []
    if fmt == "tar":
        with tarfile.open(dest_path, "w:gz") as archive:
            for item in items:
                sha = _add_tar_member(archive, item)
                manifest.append({"path": item["arcname"], "sha256": sha, "size": item["size"],
                                  "kind": item["kind"], "db_id": item["db_id"]})
            manifest_bytes = _manifest_bytes(manifest)
            info = tarfile.TarInfo(name="manifest.json")
            info.size = len(manifest_bytes)
            archive.addfile(info, io.BytesIO(manifest_bytes))
    elif fmt == "zip":
        with zipfile.ZipFile(dest_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in items:
                sha = _add_zip_member(archive, item)
                manifest.append({"path": item["arcname"], "sha256": sha, "size": item["size"],
                                  "kind": item["kind"], "db_id": item["db_id"]})
            archive.writestr("manifest.json", _manifest_bytes(manifest))
    else:
        raise ValueError(f"Unknown format '{fmt}'")
    return manifest


def archive_filename(scope, fmt):
    ext = "zip" if fmt == "zip" else "tar.gz"
    return f"backdeezup-export-{scope}.{ext}"


def archive_content_type(fmt):
    return "application/zip" if fmt == "zip" else "application/gzip"
