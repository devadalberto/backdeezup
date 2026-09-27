"""User-facing status labels for backed-up items (Phase 26). Display only.

One dict maps the existing ``State`` values (DriveAsset in
google_media_backup/models.py, GmailMessage in google_gmail_backup/models.py)
to plain-language labels. Unknown states render their raw value, never crash.

"Safe to delete remotely" mirrors the two proofs ``sync_verify`` checks before
a Drive asset becomes VERIFIED (google_media_backup/api.py): the downloaded
file exists on disk AND the asset is linked to a MediaItem. Gmail has a single
proof (``raw_path``), so it never gets that label.
"""
import os

STATE_LABELS = {
    "DISCOVERED": "Discovered",
    "DOWNLOADED": "Downloaded",
    "VERIFIED": "Verified",
    "IMPORTED": "Imported",
    "DELETE_PENDING": "Deletion pending",
    "DELETED": "Deleted remotely",
    "TRASHED": "In Gmail trash",
    "SOFT_DELETED": "Gone from Gmail (backup kept)",
}
SAFE_TO_DELETE = "Safe to delete remotely"
FAILED = "Failed"

# chip colour class per label kind
_KIND = {
    "VERIFIED": "ok",
    "DELETE_PENDING": "warn",
    "DELETED": "muted",
    "TRASHED": "muted",
    "SOFT_DELETED": "muted",
}


def state_label(state):
    """Label for a bare State value; unknown values come back unchanged."""
    return STATE_LABELS.get(state, "" if state is None else str(state))


def _has_both_proofs(item):
    path = getattr(item, "download_path", None)
    try:
        return bool(path and os.path.exists(path) and getattr(item, "media_item_id", None))
    except OSError:
        return False


def item_label(item):
    """``{"label", "kind"}`` for one DriveAsset / GmailMessage-like object.

    Precedence: Failed (existing ``error`` field) > Safe to delete remotely
    (Drive VERIFIED with both proofs) > plain state label.
    """
    state = getattr(item, "state", None)
    if getattr(item, "error", None):
        return {"label": FAILED, "kind": "fail"}
    if state == "VERIFIED" and _has_both_proofs(item):
        return {"label": SAFE_TO_DELETE, "kind": "ok"}
    return {"label": state_label(state), "kind": _KIND.get(state, "neutral")}
