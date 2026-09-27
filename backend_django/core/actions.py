"""Dashboard action buttons (Phase 27).

Every action enqueues EXISTING Celery tasks with ``.delay()`` (or a chain of
them). Guards: a Redis lock per action (the E4 helper from
google_gmail_backup.tasks) so a double-click does not double-enqueue, and a
``jobs_paused`` flag the buttons respect. Pausing never revokes running tasks
and never touches Beat.
"""
from celery import chain
from django.core.cache import cache

from core.storage import guard_block_reason
from google_gmail_backup.tasks import _acquire_lock

PAUSE_KEY = "backdeezup:jobs_paused"
LOCK_TTL_SECONDS = 60

#: actions that enqueue a download step (Phase 32 storage guard applies to these).
DOWNLOAD_ACTIONS = {"gmail-backup", "drive-backup", "photos-backup", "retry-failed"}


def _gmail_backup():
    from google_gmail_backup.tasks import task_gmail_download_batch, task_gmail_incremental_sync
    return chain(task_gmail_incremental_sync.si(), task_gmail_download_batch.si()).delay()


def _drive_backup():
    from google_media_backup.tasks import task_docs_discover, task_docs_download_batch
    return chain(task_docs_discover.si(), task_docs_download_batch.si()).delay()


def _photos_backup():
    from google_media_backup.tasks import task_photos_discover, task_photos_download_batch
    return chain(task_photos_discover.si(), task_photos_download_batch.si()).delay()


def _verify_files():
    from core.tasks import task_verify_files
    return task_verify_files.delay()


def _import_media():
    from core.tasks import task_import_media
    return task_import_media.delay()


def _restore_smoke_test():
    from core.tasks import task_restore_smoke_test
    return task_restore_smoke_test.delay()


def _retry_failed():
    """Failed items keep their pre-failure state, so re-running download + verify retries them."""
    from core.tasks import task_verify_files
    from google_gmail_backup.tasks import task_gmail_download_batch
    from google_media_backup.tasks import task_docs_download_batch, task_photos_download_batch
    return chain(
        task_photos_download_batch.si(), task_docs_download_batch.si(),
        task_gmail_download_batch.si(), task_verify_files.si(),
    ).delay()


ACTIONS = {
    "gmail-backup": ("Gmail backup", _gmail_backup),
    "drive-backup": ("Drive backup", _drive_backup),
    "photos-backup": ("Photos backup", _photos_backup),
    "verify-files": ("Verify files", _verify_files),
    "import-media": ("Import media", _import_media),
    "retry-failed": ("Retry failed", _retry_failed),
    "restore-smoke-test": ("Can I restore a file?", _restore_smoke_test),
}


def is_paused():
    return bool(cache.get(PAUSE_KEY))


def set_paused(value):
    if value:
        cache.set(PAUSE_KEY, "1", None)
    else:
        cache.delete(PAUSE_KEY)


def run_action(name):
    """Returns ``(http_status, payload)``."""
    if name == "pause":
        set_paused(True)
        return 200, {"ok": True, "message": "Jobs paused. Dashboard buttons will not enqueue new work."}
    if name == "resume":
        set_paused(False)
        return 200, {"ok": True, "message": "Jobs resumed."}
    if name not in ACTIONS:
        return 404, {"ok": False, "message": f"Unknown action '{name}'."}
    label, enqueue = ACTIONS[name]
    if is_paused():
        return 409, {"ok": False, "message": f"{label}: jobs are paused. Resume first."}
    if name in DOWNLOAD_ACTIONS:
        reason = guard_block_reason()
        if reason:
            return 409, {"ok": False, "message": f"{label}: refused -- {reason}"}
    if not _acquire_lock(f"dashboard:{name}", LOCK_TTL_SECONDS):
        return 409, {"ok": False, "message": f"{label}: already running (started within the last {LOCK_TTL_SECONDS}s)."}
    result = enqueue()
    return 202, {"ok": True, "message": f"{label} queued.", "task_id": result.id}
