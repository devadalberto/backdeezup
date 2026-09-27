"""Restore backed-up files to a local directory (Phase 37).

Writes ONLY inside ``settings.RESTORE_ROOT`` -- ``resolve_dest_root`` rejects
any destination (including a ``../`` traversal attempt) that resolves outside
it. Never touches Gmail or Drive (restore-to-source is Phase 14 / backlog);
this only copies the already-downloaded local file to a new local location.
"""
import hashlib
import os
import shutil

from django.conf import settings

CHUNK_SIZE = 256 * 1024

ON_CONFLICT_CHOICES = ("skip", "overwrite", "rename", "compare")


def _restore_root():
    root = os.path.realpath(getattr(settings, "RESTORE_ROOT", None) or os.path.join(settings.MEDIA_ROOT, "restores"))
    os.makedirs(root, exist_ok=True)
    return root


def resolve_dest_root(dest_subdir=""):
    """Returns the absolute, existing directory ``RESTORE_ROOT/dest_subdir``.
    Raises ValueError if the resolved path is not inside RESTORE_ROOT."""
    root = _restore_root()
    candidate = os.path.realpath(os.path.join(root, dest_subdir or ""))
    if candidate != root and not candidate.startswith(root + os.sep):
        raise ValueError(f"Destination '{dest_subdir}' resolves outside RESTORE_ROOT.")
    os.makedirs(candidate, exist_ok=True)
    return candidate


def sha256_file(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _preferred_mtime(item):
    """The stored metadata date where we have one (Gmail's Date header),
    else the source file's own on-disk mtime -- always available."""
    if item["kind"] == "gmail":
        from google_gmail_backup.models import GmailMessage

        date = GmailMessage.objects.filter(pk=item["db_id"]).values_list("date", flat=True).first()
        if date:
            return date.timestamp()
    return os.path.getmtime(item["disk_path"])


def _next_available_name(path):
    base, ext = os.path.splitext(path)
    n = 1
    candidate = f"{base} ({n}){ext}"
    while os.path.exists(candidate):
        n += 1
        candidate = f"{base} ({n}){ext}"
    return candidate


def _copy_one(item, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    shutil.copyfile(item["disk_path"], dest_path)
    mtime = _preferred_mtime(item)
    os.utime(dest_path, (mtime, mtime))


def restore_items(items, dest_subdir="", on_conflict="skip"):
    """items: the list of dicts core.export.resolve_export_items returns
    (kind, db_id, arcname, disk_path, size). Returns one result dict per item:
    {"arcname", "action": "copied"|"skipped"|"overwritten"|"renamed", "dest_path"}.
    """
    if on_conflict not in ON_CONFLICT_CHOICES:
        raise ValueError(f"on_conflict must be one of {ON_CONFLICT_CHOICES}")

    dest_root = resolve_dest_root(dest_subdir)
    results = []

    for item in items:
        dest_path = os.path.realpath(os.path.join(dest_root, item["arcname"]))
        if dest_path != dest_root and not dest_path.startswith(dest_root + os.sep):
            raise ValueError(f"Item path '{item['arcname']}' resolves outside the restore destination.")

        if not os.path.exists(dest_path):
            _copy_one(item, dest_path)
            results.append({"arcname": item["arcname"], "action": "copied", "dest_path": dest_path})
            continue

        if on_conflict == "skip":
            results.append({"arcname": item["arcname"], "action": "skipped", "dest_path": dest_path})
            continue

        if on_conflict == "overwrite":
            _copy_one(item, dest_path)
            results.append({"arcname": item["arcname"], "action": "overwritten", "dest_path": dest_path})
            continue

        if on_conflict == "rename":
            new_path = _next_available_name(dest_path)
            _copy_one(item, new_path)
            results.append({"arcname": item["arcname"], "action": "renamed", "dest_path": new_path})
            continue

        # compare: skip when sha256 equal, else rename
        if sha256_file(dest_path) == sha256_file(item["disk_path"]):
            results.append({"arcname": item["arcname"], "action": "skipped", "dest_path": dest_path})
        else:
            new_path = _next_available_name(dest_path)
            _copy_one(item, new_path)
            results.append({"arcname": item["arcname"], "action": "renamed", "dest_path": new_path})

    return results
