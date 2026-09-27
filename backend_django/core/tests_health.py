"""Phase 24 — system health page tests."""
import pytest
from django.contrib.auth import get_user_model

from core import health


@pytest.fixture
def staff_client(client, db):
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_json_requires_staff(client):
    assert client.get("/health/json/").status_code == 403


@pytest.mark.django_db
def test_page_requires_staff(client):
    resp = client.get("/health/")
    assert resp.status_code == 302 and "login" in resp["Location"]


@pytest.mark.django_db
def test_json_parses_with_every_check(staff_client):
    resp = staff_client.get("/health/json/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"ok", "warn", "fail"}
    assert {c["key"] for c in data["checks"]} == {k for k, _, _ in health.CHECKS}
    assert all(c["status"] in {"ok", "warn", "fail"} and c["detail"] for c in data["checks"])
    assert next(c for c in data["checks"] if c["key"] == "database")["status"] == "ok"


@pytest.mark.django_db
def test_page_200(staff_client):
    resp = staff_client.get("/health/")
    assert resp.status_code == 200
    assert b"System health" in resp.content


@pytest.mark.django_db
def test_failing_check_does_not_break_page(staff_client, monkeypatch):
    def boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr(health, "CHECKS", [("redis", "Redis", boom), ("version", "App version", health.check_version)])
    resp = staff_client.get("/health/json/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "fail"
    redis_row = data["checks"][0]
    assert redis_row["status"] == "fail" and redis_row["detail"]
    assert data["checks"][1]["status"] == "ok"
    assert staff_client.get("/health/").status_code == 200


@pytest.mark.parametrize("statuses,expected", [
    (["ok", "ok"], "ok"), (["ok", "warn"], "warn"), (["warn", "fail", "ok"], "fail"),
])
def test_overall_status(statuses, expected):
    assert health.overall_status([{"status": s} for s in statuses]) == expected


def test_media_write_check(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    status, _ = health.check_media_write()
    assert status == "ok" and list(tmp_path.iterdir()) == []


@pytest.mark.django_db
def test_health_json_includes_storage_guard_banner(staff_client, settings, monkeypatch):
    from collections import namedtuple

    from core import storage

    Usage = namedtuple("Usage", "total used free")
    settings.STORAGE_PAUSE_PCT = 1
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p: Usage(100, 50, 50))
    data = staff_client.get("/health/json/").json()
    assert data["storage_guard"]["level"] == "pause"


def test_storage_thresholds(settings, tmp_path, monkeypatch):
    from collections import namedtuple
    settings.MEDIA_ROOT = str(tmp_path)
    Usage = namedtuple("Usage", "total used free")
    for free, expected in [(50, "ok"), (5, "warn"), (1, "fail")]:
        monkeypatch.setattr(health.shutil, "disk_usage", lambda p, f=free: Usage(100, 100 - f, f))
        assert health.check_storage()[0] == expected
