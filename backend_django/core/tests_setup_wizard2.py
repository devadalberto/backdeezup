"""Phase 30 — setup wizard part 2 (steps 3-7) and the full end-to-end flow.

Wizard flow/guard logic is tested with core.setup.test_backup.run_test_backup,
core.setup.schedule.apply_schedule and core.oauth mocked out -- those have
their own dedicated tests (below, and in tests_oauth.py) that exercise the
real pipeline/Celery/Beat/OAuth code. Here we only prove the wizard wires them
correctly: guards, step advancement, session/state data, and completion.
"""
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from core import models as core_models


def _state_at(step, **extra):
    state, _ = core_models.SetupState.objects.update_or_create(pk=1, defaults={"step": step, **extra})
    return state


def _create_admin_and_login(client):
    """Drives the wizard through steps 1-2 for real, landing at 'services' with
    the new admin already logged in -- the precondition every later-step test needs."""
    _state_at("admin")
    resp = client.post("/setup/admin/", {
        "username": "owner", "password1": "Sup3r-Str0ng-P@ssphrase!", "password2": "Sup3r-Str0ng-P@ssphrase!",
    })
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/services/"
    return core_models.get_or_create_state()


# ── Step 3: services ─────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_services_step_blocked_before_admin_and_reachable_after(client):
    resp = client.get("/setup/services/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/"

    _create_admin_and_login(client)
    assert client.get("/setup/services/").status_code == 200


@pytest.mark.django_db
def test_services_requires_at_least_one_and_persists_selection(client):
    _create_admin_and_login(client)

    empty = client.post("/setup/services/", {})
    assert empty.status_code == 200 and b"at least one" in empty.content.lower()

    resp = client.post("/setup/services/", {"services": ["gmail", "drive"]})
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/connect/"
    state = core_models.get_or_create_state()
    assert state.step == "connect" and state.data["services"] == ["gmail", "drive"]


# ── Step 4: connect Google (reuses Phase 28's flow) ──────────────────────────

@pytest.mark.django_db
def test_connect_step_blocked_before_services(client):
    _create_admin_and_login(client)
    resp = client.get("/setup/connect/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/services/"


@pytest.mark.django_db
def test_connect_step_shows_status_and_blocks_continue_until_connected(client):
    _create_admin_and_login(client)
    _state_at("connect")

    with patch("core.setup.views.oauth.status", return_value={"status": "fail", "detail": "no token", "scopes": []}):
        page = client.get("/setup/connect/")
        assert page.status_code == 200 and b"FAIL" in page.content
        blocked = client.post("/setup/connect/")
        assert blocked.status_code == 200 and b"Connect your Google account" in blocked.content

    with patch("core.setup.views.oauth.status", return_value={"status": "ok", "detail": "token present", "scopes": []}):
        resp = client.post("/setup/connect/")
        assert resp.status_code == 302 and resp.headers["Location"] == "/setup/storage/"
    assert core_models.get_or_create_state().step == "storage"


@pytest.mark.django_db
def test_connect_start_uses_oauth_start_with_wizard_return_to(client):
    _create_admin_and_login(client)
    _state_at("connect")
    with patch("core.setup.views.oauth.start", return_value="https://accounts.google.com/o/oauth2/auth?x=1") as start:
        resp = client.post("/setup/connect/start/")
    assert resp.status_code == 302 and resp["Location"].startswith("https://accounts.google.com")
    start.assert_called_once()
    assert start.call_args.kwargs.get("return_to") == "setup_connect"


@pytest.mark.django_db
def test_full_oauth_round_trip_returns_to_wizard_not_dashboard(client):
    """core.oauth.start(return_to='setup_connect') -> Google -> callback lands back
    on /setup/connect/, not /dashboard/connect/ (Phase 28's default)."""
    _create_admin_and_login(client)
    _state_at("connect")
    from core import oauth
    from django.utils import timezone

    session = client.session
    session[oauth.SESSION_STATE_KEY] = "abc123"
    session[oauth.SESSION_REDIRECT_KEY] = "http://testserver/api/oauth/callback"
    session[oauth.SESSION_STARTED_KEY] = timezone.now().isoformat()
    session[oauth.SESSION_RETURN_KEY] = "setup_connect"
    session.save()

    fake_creds = MagicMock(to_json=lambda: "{}")
    with patch.object(oauth, "_build_flow") as build, patch.object(oauth, "_save_creds"):
        build.return_value = MagicMock(credentials=fake_creds)
        resp = client.get("/api/oauth/callback", {"code": "x", "state": "abc123"})
    assert resp.status_code == 302 and resp["Location"] == "/setup/connect/"
    assert oauth.SESSION_RETURN_KEY not in client.session


# ── Step 5: storage ───────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_storage_step_blocks_continue_when_not_writable(client):
    _create_admin_and_login(client)
    _state_at("storage")

    with patch("core.setup.views.check_media_write", return_value=("fail", "disk full")), \
         patch("core.setup.views.check_storage", return_value=("ok", "10GB free")):
        page = client.get("/setup/storage/")
        assert page.status_code == 200 and b"disk full" in page.content
        blocked = client.post("/setup/storage/")
        assert blocked.status_code == 200
    assert core_models.get_or_create_state().step == "storage"


@pytest.mark.django_db
def test_storage_step_continues_when_writable(client):
    _create_admin_and_login(client)
    _state_at("storage")
    with patch("core.setup.views.check_media_write", return_value=("ok", "wrote fine")), \
         patch("core.setup.views.check_storage", return_value=("ok", "10GB free")):
        resp = client.post("/setup/storage/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/schedule/"
    assert core_models.get_or_create_state().step == "schedule"


# ── Step 6: schedule ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_schedule_step_rejects_bad_time_and_accepts_good_one(client):
    _create_admin_and_login(client)
    _state_at("schedule")

    bad = client.post("/setup/schedule/", {"preset": "daily", "time": "25:99"})
    assert bad.status_code == 200 and b"valid 24-hour time" in bad.content

    with patch("core.setup.views.apply_schedule") as apply_mock:
        resp = client.post("/setup/schedule/", {"preset": "weekly", "time": "03:30"})
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/test/"
    apply_mock.assert_called_once_with("weekly", 3, 30)
    state = core_models.get_or_create_state()
    assert state.step == "test" and state.data["schedule"] == {"preset": "weekly", "time": "03:30"}


@pytest.mark.django_db
def test_schedule_step_shows_humanized_error_without_advancing(client):
    _create_admin_and_login(client)
    _state_at("schedule")
    with patch("core.setup.views.apply_schedule", side_effect=ConnectionError("redis down")):
        resp = client.post("/setup/schedule/", {"preset": "daily", "time": "02:00"})
    assert resp.status_code == 200 and b"unreachable" in resp.content.lower()
    assert core_models.get_or_create_state().step == "schedule"


# ── Step 7: test backup ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_test_step_success_completes_the_wizard(client):
    _create_admin_and_login(client)
    _state_at("test", data={"services": ["drive"]})

    success = {"discovered": 3, "verified": 2, "errors": [], "success": True}
    with patch("core.setup.views.run_test_backup", return_value=success) as run:
        resp = client.post("/setup/test/")
    assert resp.status_code == 200 and b"Backup is working" in resp.content
    run.assert_called_once_with(["drive"], limit=10)

    state = core_models.get_or_create_state()
    assert state.completed is True and state.step == "done"
    assert core_models.is_first_run() is False
    assert client.get("/dashboard/").status_code == 200
    assert client.get("/setup/").headers["Location"] == "/dashboard/"


@pytest.mark.django_db
def test_test_step_failure_does_not_complete_and_allows_retry(client):
    _create_admin_and_login(client)
    _state_at("test", data={"services": ["gmail"]})

    failure = {"discovered": 0, "verified": 0, "errors": [], "success": False}
    with patch("core.setup.views.run_test_backup", return_value=failure):
        resp = client.post("/setup/test/")
    assert resp.status_code == 200 and b"Retry test backup" in resp.content
    assert b"No items were found" in resp.content

    state = core_models.get_or_create_state()
    assert state.completed is False and state.step == "test"
    assert core_models.is_first_run() is True
    assert client.get("/setup/test/").status_code == 200


@pytest.mark.django_db
def test_test_step_crash_is_humanized_not_a_500(client):
    _create_admin_and_login(client)
    _state_at("test", data={"services": ["drive"]})
    with patch("core.setup.views.run_test_backup", side_effect=ConnectionError("redis down")):
        resp = client.post("/setup/test/")
    assert resp.status_code == 200
    assert core_models.get_or_create_state().completed is False


# ── Full 7-step flow, end to end ──────────────────────────────────────────────

@pytest.mark.django_db
def test_full_wizard_flow_end_to_end(client):
    """Fresh DB -> every step, mocking only the three external boundaries
    (Google OAuth, Beat, and the pipelines) -> completed=True, dashboard loads,
    /setup/ locked afterward. Mirrors the plan's own verify step."""
    assert client.get("/setup/").status_code == 200

    ok_checks = [{"key": "database", "label": "Database", "status": "ok", "detail": "fine"}]
    with patch("core.setup.views.run_checks", return_value=ok_checks), \
         patch("core.setup.views.oauth.status", return_value={"status": "ok", "detail": "ok", "scopes": []}), \
         patch("core.setup.views.apply_schedule"), \
         patch("core.setup.views.run_test_backup", return_value={"discovered": 5, "verified": 5, "errors": [], "success": True}):

        assert client.post("/setup/").status_code == 302  # welcome -> admin

        resp = client.post("/setup/admin/", {
            "username": "owner", "email": "o@example.com",
            "password1": "Sup3r-Str0ng-P@ssphrase!", "password2": "Sup3r-Str0ng-P@ssphrase!",
        })
        assert resp.status_code == 302 and resp.headers["Location"] == "/setup/services/"

        resp = client.post("/setup/services/", {"services": ["gmail", "drive", "photos"]})
        assert resp.status_code == 302 and resp.headers["Location"] == "/setup/connect/"

        resp = client.post("/setup/connect/")
        assert resp.status_code == 302 and resp.headers["Location"] == "/setup/storage/"

        with patch("core.setup.views.check_media_write", return_value=("ok", "fine")), \
             patch("core.setup.views.check_storage", return_value=("ok", "fine")):
            resp = client.post("/setup/storage/")
        assert resp.status_code == 302 and resp.headers["Location"] == "/setup/schedule/"

        resp = client.post("/setup/schedule/", {"preset": "daily", "time": "02:00"})
        assert resp.status_code == 302 and resp.headers["Location"] == "/setup/test/"

        resp = client.post("/setup/test/")
        assert resp.status_code == 200 and b"Backup is working" in resp.content

    user = get_user_model().objects.get(username="owner")
    assert user.is_superuser
    state = core_models.get_or_create_state()
    assert state.completed is True and state.step == "done"

    assert client.get("/dashboard/").status_code == 200
    assert client.get("/setup/").headers["Location"] == "/dashboard/"
    for url in ("/setup/services/", "/setup/connect/", "/setup/storage/", "/setup/schedule/", "/setup/test/"):
        assert client.get(url).headers["Location"] == "/dashboard/"
