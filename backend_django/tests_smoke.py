"""Smoke tests — quick sanity checks that run in CI."""
import pytest


@pytest.mark.smoke
def test_django_check(settings):
    """Django system check passes with no errors."""
    from django.core.management import call_command
    call_command("check", "--fail-level", "ERROR")


@pytest.mark.smoke
def test_celery_gmail_tasks_importable():
    """Gmail Celery tasks can be imported without error."""
    from google_gmail_backup.tasks import (
        task_gmail_incremental_sync,
        task_apply_protected_senders,
        task_run_cleanup_rules,
        task_gmail_reconcile,
        task_purge_expired_soft_deletes,
    )
    assert callable(task_gmail_incremental_sync)
    assert callable(task_gmail_reconcile)


@pytest.mark.smoke
def test_celery_media_tasks_importable():
    """Media Celery tasks can be imported without error."""
    from google_media_backup.tasks import (
        task_photos_discover,
        task_photos_download_batch,
        task_docs_discover,
        task_docs_download_batch,
        task_docs_import_vault,
        task_drive_commit_delete,
    )
    assert callable(task_photos_discover)
    assert callable(task_docs_discover)


@pytest.mark.smoke
def test_models_importable():
    """All app models import without error."""
    from google_gmail_backup.models import (
        GmailMessage, GmailSyncState, CleanupRule,
        ProtectedSender, CleanupAuditLog, GmailAttachment,
    )
    from google_media_backup.models import DriveAsset, MediaItem, RunLog
    from media_vault.models import VaultImage, VaultMedia, VaultDocument
    assert GmailMessage.STATE_VERIFIED == "VERIFIED"
    assert DriveAsset.State.DISCOVERED == "DISCOVERED"
