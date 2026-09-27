"""Phase 30 — direct unit tests for the pieces setup/views.py wires together:
core.setup.schedule (writes Beat entries), core.setup.test_backup (runs the
pipelines synchronously), and the two new forms. No HTTP client here --
core/tests_setup_wizard2.py covers the wizard's own guard/flow logic with
these mocked out.
"""
from unittest.mock import patch

import pytest

from core.setup.forms import ScheduleForm, ServicesForm
from core.setup.schedule import BEAT_TASK_NAMES, apply_schedule
from core.setup.test_backup import run_test_backup


# ── ServicesForm / ScheduleForm ───────────────────────────────────────────────

def test_services_form_requires_at_least_one():
    form = ServicesForm(data={})
    assert not form.is_valid() and "at least one" in str(form.errors)


def test_services_form_accepts_valid_subset():
    form = ServicesForm(data={"services": ["gmail"]})
    assert form.is_valid() and form.cleaned_data["services"] == ["gmail"]


@pytest.mark.parametrize("time,ok", [("02:00", True), ("23:59", True), ("00:00", True), ("9:5", True),
                                      ("24:00", False), ("abc", False), ("12:60", False)])
def test_schedule_form_time_validation(time, ok):
    form = ScheduleForm(data={"preset": "daily", "time": time})
    assert form.is_valid() is ok


def test_schedule_form_exposes_parsed_hour_minute():
    form = ScheduleForm(data={"preset": "weekly", "time": "03:45"})
    assert form.is_valid()
    assert (form.cleaned_data["hour"], form.cleaned_data["minute"]) == (3, 45)


# ── apply_schedule ─────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_apply_schedule_writes_the_same_named_beat_entries():
    from django_celery_beat.models import PeriodicTask

    apply_schedule("daily", 2, 0)
    tasks = {pt.name: pt.task for pt in PeriodicTask.objects.filter(name__in=BEAT_TASK_NAMES)}
    assert tasks == BEAT_TASK_NAMES
    for pt in PeriodicTask.objects.filter(name__in=BEAT_TASK_NAMES):
        assert pt.enabled is True
        assert pt.crontab.hour == "2" and pt.crontab.minute == "0" and pt.crontab.day_of_week == "*"


@pytest.mark.django_db
def test_apply_schedule_weekly_uses_monday_and_is_idempotent():
    from django_celery_beat.models import PeriodicTask

    apply_schedule("weekly", 3, 30)
    apply_schedule("weekly", 3, 30)  # re-applying must not create duplicates
    assert PeriodicTask.objects.filter(name__in=BEAT_TASK_NAMES).count() == len(BEAT_TASK_NAMES)
    pt = PeriodicTask.objects.get(name="gmail-incremental-sync")
    assert pt.crontab.day_of_week == "1"


@pytest.mark.django_db
def test_apply_schedule_rejects_unknown_preset():
    with pytest.raises(ValueError):
        apply_schedule("hourly", 0, 0)


@pytest.mark.django_db
def test_apply_schedule_uses_configured_time_zone(settings):
    from django_celery_beat.models import CrontabSchedule

    settings.TIME_ZONE = "America/Los_Angeles"
    apply_schedule("daily", 4, 0)
    assert CrontabSchedule.objects.get(hour="4", minute="0").timezone.key == "America/Los_Angeles"


# ── run_test_backup ────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_run_test_backup_no_services_selected():
    result = run_test_backup([])
    assert result == {
        "started_at": result["started_at"], "services": [], "discovered": 0, "verified": 0,
        "drive": {"discovered": 0, "verified": 0}, "gmail": {"discovered": 0, "verified": 0},
        "errors": [], "success": False,
    }


@pytest.mark.django_db
def test_run_test_backup_records_a_humanized_error_per_failing_service():
    with patch("core.setup.test_backup._run_drive_pipeline", side_effect=ConnectionError("redis down")), \
         patch("core.setup.test_backup._run_gmail_pipeline", side_effect=ValueError("Not authenticated.")):
        result = run_test_backup(["drive", "gmail"], limit=5)
    assert result["success"] is False
    sources = {e["source"] for e in result["errors"]}
    assert sources == {"Drive", "Gmail"}
    assert all(e.get("title") for e in result["errors"])


@pytest.mark.django_db
def test_run_test_backup_success_end_to_end_drive(tmp_path, monkeypatch):
    """Real discover -> download -> verify through drive_pipeline's own Command
    code (core.setup.test_backup just call_command()s it), with only the two
    Google API functions mocked -- list_drive_files (discovery) and
    download_file (the actual transfer) -- proves the real counting/state
    transitions, not a re-implementation of them."""
    import google_media_backup.utils as gmb_utils
    monkeypatch.setattr(gmb_utils, "MEDIA_ROOT", tmp_path)

    def _fake_download(file_id, out_path):
        with open(out_path, "wb") as f:
            f.write(b"fake file bytes")
        return True

    with patch("google_media_backup.services_google.list_drive_files",
               return_value=([{"id": "f1", "name": "photo.jpg", "mimeType": "image/jpeg", "size": 0}], None)), \
         patch("google_media_backup.services_google.download_file", side_effect=_fake_download):
        result = run_test_backup(["drive"], limit=10)

    assert result["errors"] == []
    assert result["drive"]["discovered"] == 1
    assert result["drive"]["verified"] == 1
    assert result["verified"] == 1
    assert result["success"] is True

    from google_media_backup.models import DriveAsset
    asset = DriveAsset.objects.get(drive_id="f1")
    assert asset.state == DriveAsset.State.VERIFIED
    assert asset.download_path and open(asset.download_path, "rb").read() == b"fake file bytes"
