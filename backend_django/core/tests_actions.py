"""Phase 27 — dashboard action button tests."""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from core import actions

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "p27"}}


@pytest.fixture(autouse=True)
def local_cache(settings):
    settings.CACHES = LOCMEM
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def staff_client(db):
    c = Client(enforce_csrf_checks=False)
    c.force_login(get_user_model().objects.create_user("s", password="x", is_staff=True))
    return c


@pytest.fixture
def fake_enqueue():
    """Replace every action's enqueue with a mock returning a task id."""
    mock = MagicMock(return_value=MagicMock(id="task-123"))
    table = {name: (label, mock) for name, (label, _) in actions.ACTIONS.items()}
    with patch.dict(actions.ACTIONS, table, clear=True):
        yield mock


@pytest.mark.django_db
def test_get_not_allowed_and_anonymous_redirected(client, staff_client):
    assert staff_client.get("/dashboard/actions/verify-files/").status_code == 405
    resp = client.post("/dashboard/actions/verify-files/")
    assert resp.status_code == 302 and "login" in resp["Location"]


@pytest.mark.django_db
def test_csrf_enforced(db):
    c = Client(enforce_csrf_checks=True)
    c.force_login(get_user_model().objects.create_user("s2", password="x", is_staff=True))
    assert c.post("/dashboard/actions/verify-files/").status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["gmail-backup", "drive-backup", "photos-backup", "verify-files", "import-media", "retry-failed"])
def test_each_action_enqueues_once_and_returns_task_id(staff_client, fake_enqueue, name):
    resp = staff_client.post(f"/dashboard/actions/{name}/")
    assert resp.status_code == 202
    assert resp.json()["task_id"] == "task-123"
    fake_enqueue.assert_called_once()


@pytest.mark.django_db
def test_double_click_says_already_running(staff_client, fake_enqueue):
    assert staff_client.post("/dashboard/actions/verify-files/").status_code == 202
    second = staff_client.post("/dashboard/actions/verify-files/")
    assert second.status_code == 409 and "already running" in second.json()["message"]
    assert fake_enqueue.call_count == 1
    # a different action has its own lock
    assert staff_client.post("/dashboard/actions/import-media/").status_code == 202


@pytest.mark.django_db
def test_pause_blocks_buttons_and_resume_restores(staff_client, fake_enqueue):
    assert staff_client.post("/dashboard/actions/pause/").status_code == 200
    blocked = staff_client.post("/dashboard/actions/verify-files/")
    assert blocked.status_code == 409 and "paused" in blocked.json()["message"]
    fake_enqueue.assert_not_called()
    assert staff_client.post("/dashboard/actions/resume/").status_code == 200
    assert staff_client.post("/dashboard/actions/verify-files/").status_code == 202


@pytest.mark.django_db
def test_storage_guard_blocks_download_actions_only(staff_client, fake_enqueue, settings, monkeypatch):
    from collections import namedtuple

    from core import storage

    Usage = namedtuple("Usage", "total used free")
    settings.STORAGE_PAUSE_PCT = 1
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: Usage(100, 50, 50))

    resp = staff_client.post("/dashboard/actions/drive-backup/")
    assert resp.status_code == 409 and "low disk" in resp.json()["message"]
    fake_enqueue.assert_not_called()
    # verify-files does not download, so the guard does not apply to it
    assert staff_client.post("/dashboard/actions/verify-files/").status_code == 202


@pytest.mark.django_db
def test_unknown_action_404(staff_client):
    assert staff_client.post("/dashboard/actions/execute-cleanup/").status_code == 404


@pytest.mark.django_db
def test_broker_failure_is_humanized_503(staff_client):
    boom = MagicMock(side_effect=ConnectionError("redis down"))
    with patch.dict(actions.ACTIONS, {"verify-files": ("Verify files", boom)}):
        resp = staff_client.post("/dashboard/actions/verify-files/")
    assert resp.status_code == 503 and resp.json()["message"]


@pytest.mark.django_db
def test_htmx_request_gets_html_fragment(staff_client, fake_enqueue):
    resp = staff_client.post("/dashboard/actions/verify-files/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200 and b"task-123" in resp.content


def test_real_actions_call_delay_on_existing_tasks():
    with patch("core.tasks.task_verify_files") as t:
        t.delay.return_value = MagicMock(id="x")
        actions._verify_files()
        t.delay.assert_called_once_with()


@pytest.mark.django_db
def test_progress_card_shows_dashes_when_not_computable(staff_client):
    from google_media_backup.models import RunLog
    RunLog.objects.create(run_id="r", status="OK", totals={"downloaded": 3, "verified": 2}, error_log=[{"error": "x"}])
    html = staff_client.get("/dashboard/cards/").content.decode()
    assert "5 done" in html and "-- skipped" in html and "1 failed" in html and "ETA --" in html
    assert "hx-post" in staff_client.get("/dashboard/").content.decode()


@pytest.mark.django_db
def test_wrapper_tasks_run_existing_commands_on_empty_db():
    from core.tasks import task_import_media, task_verify_files
    assert task_verify_files.apply().get()["limit"] == 500
    assert task_import_media.apply().get() == {"import_media": "done"}


def test_chains_build_from_existing_tasks():
    from celery import chain
    with patch.object(chain, "delay", create=True):
        pass  # construction-only: building the signatures must not raise
    from core.tasks import task_verify_files
    from google_gmail_backup.tasks import task_gmail_download_batch, task_gmail_incremental_sync
    from google_media_backup.tasks import task_docs_discover, task_docs_download_batch, task_photos_discover, task_photos_download_batch
    for sigs in ((task_gmail_incremental_sync, task_gmail_download_batch),
                 (task_docs_discover, task_docs_download_batch),
                 (task_photos_discover, task_photos_download_batch),
                 (task_photos_download_batch, task_docs_download_batch, task_gmail_download_batch, task_verify_files)):
        assert len(chain(*[t.si() for t in sigs]).tasks) == len(sigs)
