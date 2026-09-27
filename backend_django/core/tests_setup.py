"""Phase 29 — setup wizard tests."""
import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from core import models as core_models
from core.setup import validators as v


@pytest.mark.django_db
def test_wizard_reachable_on_fresh_db(client):
    resp = client.get("/setup/")
    assert resp.status_code == 200
    assert b"SETUP" in resp.content


@pytest.mark.django_db
def test_wizard_never_reachable_when_superuser_exists(client):
    get_user_model().objects.create_superuser("admin", "a@b.c", "unguessable-pw-482913!")
    assert client.get("/setup/").status_code == 302
    assert client.get("/setup/").headers["Location"] == "/dashboard/"
    assert client.get("/setup/admin/").status_code == 302


@pytest.mark.django_db
def test_wizard_never_reachable_after_completion_even_if_admin_deleted(client):
    core_models.SetupState.objects.create(pk=1, completed=True, step="done")
    assert core_models.is_first_run() is False
    assert client.get("/setup/").status_code == 302
    assert client.get("/setup/admin/").status_code == 302


@pytest.mark.django_db
def test_admin_step_redirects_back_to_welcome_if_not_reached(client):
    resp = client.get("/setup/admin/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/"


@pytest.mark.django_db
def test_continue_blocked_while_a_check_fails(client, monkeypatch):
    monkeypatch.setattr(v, "CHECKS", [("redis", "Redis", lambda r: (v.FAIL, "down"))])
    resp = client.post("/setup/")
    assert resp.status_code == 200 and b"Fix the failing checks" in resp.content
    assert core_models.get_or_create_state().step == "welcome"


@pytest.mark.django_db
def test_continue_advances_step_when_all_checks_ok(client, monkeypatch):
    monkeypatch.setattr(v, "CHECKS", [("database", "Database", lambda r: (v.OK, "fine"))])
    resp = client.post("/setup/")
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/admin/"
    assert core_models.get_or_create_state().step == "admin"


@pytest.mark.django_db
def test_warn_does_not_block_continue(monkeypatch, client):
    monkeypatch.setattr(v, "CHECKS", [("tls", "TLS", lambda r: (v.WARN, "plain http"))])
    resp = client.post("/setup/")
    assert resp.status_code == 302


@pytest.mark.django_db
def test_admin_creation_logs_in_and_advances_to_services(client):
    """Phase 30 changed this hand-off: admin creation no longer completes the
    wizard by itself -- it advances to step 3 (services). See tests_setup_wizard2.py
    for the full 7-step flow through completion."""
    state = core_models.get_or_create_state()
    state.step = "admin"
    state.save()

    resp = client.post("/setup/admin/", {
        "username": "owner", "email": "owner@example.com",
        "password1": "Sup3r-Str0ng-P@ssphrase!", "password2": "Sup3r-Str0ng-P@ssphrase!",
    })
    assert resp.status_code == 302 and resp.headers["Location"] == "/setup/services/"

    user = get_user_model().objects.get(username="owner")
    assert user.is_superuser and user.is_staff
    state.refresh_from_db()
    assert state.completed is False and state.step == "services"

    # a superuser now exists, but the wizard the admin created stays reachable
    assert core_models.is_first_run() is True
    assert client.get("/setup/services/").status_code == 200
    # logged in as the new admin already (needed once later steps require staff elsewhere)
    assert client.get("/dashboard/").status_code == 200


@pytest.mark.django_db
def test_admin_form_rejects_mismatched_and_weak_passwords(client):
    core_models.SetupState.objects.create(pk=1, step="admin")
    weak = client.post("/setup/admin/", {
        "username": "owner", "password1": "password", "password2": "password",
    })
    assert weak.status_code == 200 and b"password" in weak.content.lower()
    assert get_user_model().objects.count() == 0

    mismatched = client.post("/setup/admin/", {
        "username": "owner", "password1": "Sup3r-Str0ng-P@ssphrase!", "password2": "different-one-here!",
    })
    assert mismatched.status_code == 200 and b"do not match" in mismatched.content
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_check_oauth_client_present(rf, tmp_path):
    request = rf.get("/setup/")
    with patch.object(v, "CLIENT_SECRETS", str(tmp_path / "missing.json")):
        assert v.check_oauth_client(request)[0] == v.FAIL
    secrets = tmp_path / "client.json"
    secrets.write_text(json.dumps({"installed": {"redirect_uris": ["http://x/api/oauth/callback"]}}))
    with patch.object(v, "CLIENT_SECRETS", str(secrets)):
        assert v.check_oauth_client(request)[0] == v.OK


@pytest.mark.django_db
def test_check_redirect_uri_match_and_mismatch(rf, tmp_path):
    request = rf.get("/setup/", SERVER_NAME="testserver")
    this_uri = request.build_absolute_uri("/api/oauth/callback")
    secrets = tmp_path / "client.json"
    secrets.write_text(json.dumps({"installed": {"redirect_uris": [this_uri]}}))
    with patch.object(v, "CLIENT_SECRETS", str(secrets)):
        status, detail = v.check_redirect_uri(request)
    assert status == v.OK and "registered" in detail

    secrets.write_text(json.dumps({"installed": {"redirect_uris": ["http://other-host/cb"]}}))
    with patch.object(v, "CLIENT_SECRETS", str(secrets)):
        status, detail = v.check_redirect_uri(request)
    assert status == v.WARN and "not in the registered" in detail


@pytest.mark.django_db
def test_check_tls(rf):
    plain = rf.get("/setup/")
    assert v.check_tls(plain)[0] == v.WARN
    secure = rf.get("/setup/", secure=True)
    assert v.check_tls(secure)[0] == v.OK


@pytest.mark.django_db
def test_run_checks_never_crashes_on_a_broken_check(rf, monkeypatch):
    def boom(request):
        raise ConnectionError("redis down")
    monkeypatch.setattr(v, "CHECKS", [("redis", "Redis", boom)])
    results = v.run_checks(rf.get("/setup/"))
    assert results[0]["status"] == v.FAIL and results[0]["detail"]
    assert v.can_continue(results) is False
