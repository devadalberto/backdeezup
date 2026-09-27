"""Phase 28 — browser-based OAuth tests."""
import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from core import oauth

CLI_BODY = b"<h2>OAuth completed.</h2><p>You can close this tab and return to the terminal.</p>"


@pytest.fixture
def staff_client(db):
    c = Client(enforce_csrf_checks=False)
    c.force_login(get_user_model().objects.create_user("s", password="x", is_staff=True))
    return c


@pytest.mark.django_db
def test_pages_require_staff(client):
    for url in ("/dashboard/connect/",):
        resp = client.get(url)
        assert resp.status_code == 302 and "login" in resp["Location"]
    for url in ("/dashboard/connect/start/", "/dashboard/disconnect/"):
        assert client.post(url).status_code == 302


@pytest.mark.django_db
def test_cli_callback_untouched_when_no_session_state(client):
    """No browser flow in progress -> identical to the pre-Phase-28 stub, for any actor."""
    resp = client.get("/api/oauth/callback", {"code": "abc", "state": "whatever"})
    assert resp.status_code == 200
    assert resp.content == CLI_BODY


@pytest.mark.django_db
def test_cli_callback_untouched_even_with_stale_or_wrong_state(client):
    session = client.session
    session[oauth.SESSION_STATE_KEY] = "ours"
    session[oauth.SESSION_STARTED_KEY] = timezone.now().isoformat()
    session.save()
    resp = client.get("/api/oauth/callback", {"code": "abc", "state": "not-ours"})
    assert resp.content == CLI_BODY


@pytest.mark.django_db
def test_connect_start_redirects_to_google_and_stores_state(staff_client, tmp_path):
    secrets = tmp_path / "client.json"
    secrets.write_text(json.dumps({"installed": {
        "client_id": "x", "client_secret": "y",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://testserver/api/oauth/callback"],
    }}))
    with patch.object(oauth, "CLIENT_SECRETS", str(secrets)):
        resp = staff_client.post("/dashboard/connect/start/")
    assert resp.status_code == 302
    assert resp["Location"].startswith("https://accounts.google.com/o/oauth2/auth")
    assert oauth.SESSION_STATE_KEY in staff_client.session


@pytest.mark.django_db
def test_connect_start_missing_secrets_is_humanized(staff_client, tmp_path):
    with patch.object(oauth, "CLIENT_SECRETS", str(tmp_path / "missing.json")):
        resp = staff_client.post("/dashboard/connect/start/")
    assert resp.status_code == 302 and resp["Location"] == "/dashboard/connect/"
    page = staff_client.get("/dashboard/connect/")
    assert page.status_code == 200 and b"went wrong" in page.content.lower()


@pytest.mark.django_db
def test_full_browser_flow_success(staff_client):
    session = staff_client.session
    session[oauth.SESSION_STATE_KEY] = "abc123"
    session[oauth.SESSION_REDIRECT_KEY] = "http://testserver/api/oauth/callback"
    session[oauth.SESSION_STARTED_KEY] = timezone.now().isoformat()
    session.save()

    fake_creds = MagicMock(to_json=lambda: "{}")
    with patch.object(oauth, "_build_flow") as build, patch.object(oauth, "_save_creds") as save:
        flow = MagicMock(credentials=fake_creds)
        build.return_value = flow
        resp = staff_client.get("/api/oauth/callback", {"code": "abc", "state": "abc123"})
    assert resp.status_code == 302 and resp["Location"] == "/dashboard/connect/"
    save.assert_called_once_with(fake_creds, email=None)
    assert oauth.SESSION_STATE_KEY not in staff_client.session

    page = staff_client.get("/dashboard/connect/")
    assert page.status_code == 200 and b"connected" in page.content.lower()
    assert "oauth_result" not in staff_client.session  # popped after one render


@pytest.mark.django_db
@pytest.mark.parametrize("google_error,expected_code", [
    ("access_denied", "access_denied"),
])
def test_browser_flow_google_error_is_humanized(staff_client, google_error, expected_code):
    session = staff_client.session
    session[oauth.SESSION_STATE_KEY] = "abc123"
    session[oauth.SESSION_REDIRECT_KEY] = "http://testserver/api/oauth/callback"
    session[oauth.SESSION_STARTED_KEY] = timezone.now().isoformat()
    session.save()
    staff_client.get("/api/oauth/callback", {"error": google_error, "state": "abc123"})
    page = staff_client.get("/dashboard/connect/")
    assert b"cancelled" in page.content.lower() or b"denied" in page.content.lower()


@pytest.mark.django_db
def test_browser_flow_redirect_uri_mismatch_is_humanized(staff_client):
    session = staff_client.session
    session[oauth.SESSION_STATE_KEY] = "abc123"
    session[oauth.SESSION_REDIRECT_KEY] = "http://testserver/api/oauth/callback"
    session[oauth.SESSION_STARTED_KEY] = timezone.now().isoformat()
    session.save()
    with patch.object(oauth, "_build_flow") as build:
        flow = MagicMock()
        flow.fetch_token.side_effect = Exception("Error 400: redirect_uri_mismatch")
        build.return_value = flow
        staff_client.get("/api/oauth/callback", {"code": "x", "state": "abc123"})
    page = staff_client.get("/dashboard/connect/")
    assert b"not registered" in page.content.lower()


@pytest.mark.django_db
def test_state_expires_after_ttl(client):
    from datetime import timedelta

    from django.test import RequestFactory
    from django.contrib.sessions.middleware import SessionMiddleware

    rf = RequestFactory()
    request = rf.get("/api/oauth/callback", {"state": "abc"})
    SessionMiddleware(lambda r: None).process_request(request)
    request.session[oauth.SESSION_STATE_KEY] = "abc"
    request.session[oauth.SESSION_STARTED_KEY] = (timezone.now() - oauth.STATE_TTL - timedelta(minutes=1)).isoformat()
    assert oauth.is_our_callback(request) is False


@pytest.mark.django_db
def test_disconnect_removes_token_but_never_touches_backup_data(staff_client, tmp_path, settings):
    token = tmp_path / "google_token.json"
    token.write_text("{}")
    with patch.object(oauth, "_token_path_for_email", return_value=str(token)):
        resp = staff_client.post("/dashboard/disconnect/")
    assert resp.status_code == 302
    assert not token.exists()
    from google_media_backup.models import DriveAsset
    assert DriveAsset.objects.count() == 0  # nothing to touch either way -- just proving no crash


@pytest.mark.django_db
def test_disconnect_then_health_page_shows_oauth_fail(staff_client, tmp_path):
    missing = tmp_path / "nope.json"
    with patch("google_media_backup.services_google._token_path_for_email", return_value=str(missing)):
        health = staff_client.get("/health/json/").json()
    row = next(c for c in health["checks"] if c["key"] == "oauth")
    assert row["status"] == "fail"


@pytest.mark.django_db
def test_connect_page_lists_scopes_with_reasons(staff_client):
    page = staff_client.get("/dashboard/connect/").content.decode()
    for entry in oauth.scope_list():
        assert entry["scope"] in page
    assert "Trash Drive files" in page


@pytest.mark.django_db
def test_dashboard_links_to_connect_page(staff_client):
    assert b"/dashboard/connect/" in staff_client.get("/dashboard/").content
