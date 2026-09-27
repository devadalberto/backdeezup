"""Phase 33 — stale-backup Beat check tests."""
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from core import tasks
from google_media_backup.models import RunLog


@pytest.mark.django_db
def test_disabled_by_default(settings):
    settings.NOTIFY_STALE_BACKUP_HOURS = 0
    with patch("core.notify.send") as send:
        result = tasks.task_check_backup_freshness()
    assert result == {"checked": False, "reason": "disabled"}
    send.assert_not_called()


@pytest.mark.django_db
def test_fresh_backup_does_not_notify(settings):
    settings.NOTIFY_STALE_BACKUP_HOURS = 6
    RunLog.objects.create(run_id="r1", status="OK", finished_at=timezone.now())
    with patch("core.notify.send") as send:
        result = tasks.task_check_backup_freshness()
    assert result == {"checked": True, "stale": False, "hours": 6}
    send.assert_not_called()


@pytest.mark.django_db
def test_stale_backup_notifies(settings):
    settings.NOTIFY_STALE_BACKUP_HOURS = 6
    RunLog.objects.create(run_id="r1", status="OK", finished_at=timezone.now() - timedelta(hours=10))
    with patch("core.notify.send") as send:
        result = tasks.task_check_backup_freshness()
    assert result == {"checked": True, "stale": True, "hours": 6}
    send.assert_called_once()
    assert send.call_args.args[0] == "no_successful_backup"


@pytest.mark.django_db
def test_no_runs_at_all_is_stale(settings):
    settings.NOTIFY_STALE_BACKUP_HOURS = 6
    with patch("core.notify.send") as send:
        result = tasks.task_check_backup_freshness()
    assert result["stale"] is True
    send.assert_called_once()
