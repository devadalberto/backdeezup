"""Phase 25 — unified dashboard tests."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core import dashboard
from google_gmail_backup.models import CleanupRule, GmailSyncState
from google_media_backup.models import DriveAsset, RunLog


@pytest.fixture
def staff_client(client, db):
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    client.force_login(user)
    return client


def _asset(i, state):
    return DriveAsset.objects.create(drive_id=f"d{i}", name=f"f{i}", mime_type="image/jpeg", state=state)


@pytest.mark.django_db
def test_pages_require_staff(client):
    for url in ("/dashboard/", "/dashboard/cards/"):
        resp = client.get(url)
        assert resp.status_code == 302 and "login" in resp["Location"]


@pytest.mark.django_db
def test_page_and_cards_render(staff_client):
    page = staff_client.get("/dashboard/")
    assert page.status_code == 200
    for url in ("/htmx/stats/", "/htmx/gmail/progress/", "/dashboard/cards/"):
        assert url.encode() in page.content
    cards = staff_client.get("/dashboard/cards/")
    assert cards.status_code == 200
    assert b"Backup status" in cards.content and b"Cleanup" in cards.content


@pytest.mark.django_db
def test_verified_and_sources_match_db(staff_client):
    _asset(1, "VERIFIED"); _asset(2, "VERIFIED"); _asset(3, "DISCOVERED")
    assert dashboard.verified_counts()["drive"] == DriveAsset.objects.filter(state="VERIFIED").count() == 2
    assert dashboard.items_per_source()["drive"] == DriveAsset.objects.count() == 3
    assert staff_client.get("/dashboard/cards/").status_code == 200


@pytest.mark.django_db
def test_last_successful_backup_and_duration():
    now = timezone.now()
    RunLog.objects.create(run_id="a", status="OK", started_at=now - timedelta(minutes=10), finished_at=now - timedelta(minutes=8))
    RunLog.objects.create(run_id="b", status="FAILED", started_at=now - timedelta(minutes=1), finished_at=now)
    card = dashboard.backup_status()
    assert card["latest_status"] == "FAILED"
    assert card["last_ok_duration"] == "2m 0s"


@pytest.mark.django_db
def test_cleanup_counts():
    CleanupRule.objects.create(name="a", gmail_query="q", action="trash", enabled=True)
    CleanupRule.objects.create(name="b", gmail_query="q", action="trash", enabled=False)
    card = dashboard.cleanup_state()
    assert (card["enabled"], card["disabled"]) == (1, 1)


@pytest.mark.django_db
def test_recent_errors_are_humanized():
    RunLog.objects.create(run_id="e", status="FAILED", error_log=[{"step": "x", "error": "invalid_grant: Token expired", "ts": ""}])
    GmailSyncState.objects.create(email="a@b.c", last_error="no space left on device", last_error_at=timezone.now())
    rows = dashboard.recent_errors()["rows"]
    assert {r["code"] for r in rows} == {"invalid_grant", "disk_full"}


@pytest.mark.django_db
def test_failing_card_does_not_blank_others(monkeypatch):
    def boom():
        raise ConnectionError("db gone")

    monkeypatch.setattr(dashboard, "CARDS", [("backup", boom), ("cleanup", dashboard.cleanup_state)])
    cards = dashboard.build_cards()
    assert "error" in cards["backup"] and cards["cleanup"]["enabled"] == 0


@pytest.mark.django_db
def test_storage_guard_banner_shown_when_paused(staff_client, settings, monkeypatch):
    from collections import namedtuple

    from core import storage

    Usage = namedtuple("Usage", "total used free")
    settings.STORAGE_PAUSE_PCT = 1
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: Usage(100, 50, 50))
    html = staff_client.get("/dashboard/cards/").content.decode()
    assert "STORAGE GUARD: PAUSED" in html


@pytest.mark.django_db
def test_next_run_none_without_schedule():
    assert dashboard.next_run() is None


@pytest.mark.django_db
def test_next_run_from_periodic_task():
    from django_celery_beat.models import CrontabSchedule, PeriodicTask

    cron = CrontabSchedule.objects.create(minute="0", hour="*/6", timezone="UTC")
    PeriodicTask.objects.create(name="sync", task="x.y", crontab=cron, enabled=True)
    nxt = dashboard.next_run()
    assert nxt["name"] == "sync" and nxt["when"] >= timezone.now() - timedelta(seconds=5)
