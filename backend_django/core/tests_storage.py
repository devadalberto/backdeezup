"""Phase 32 — storage guard tests."""
from collections import namedtuple
from unittest.mock import patch

import pytest

from core import storage

Usage = namedtuple("Usage", "total used free")


def _set_usage(monkeypatch, used_pct):
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda p, u=used_pct: Usage(100, u, 100 - u))


@pytest.mark.django_db
@pytest.mark.parametrize("used,expected", [(50, "ok"), (90, "warn"), (96, "pause")])
def test_status_thresholds(settings, monkeypatch, used, expected):
    settings.STORAGE_WARN_PCT = 85
    settings.STORAGE_PAUSE_PCT = 95
    _set_usage(monkeypatch, used)
    assert storage.status()[0] == expected


@pytest.mark.django_db
def test_guard_block_reason_respects_enabled_flag(settings, monkeypatch):
    settings.STORAGE_PAUSE_PCT = 1
    _set_usage(monkeypatch, 50)
    settings.STORAGE_GUARD_ENABLED = True
    assert storage.guard_block_reason() and "low disk" in storage.guard_block_reason()
    settings.STORAGE_GUARD_ENABLED = False
    assert storage.guard_block_reason() is None


@pytest.mark.django_db
def test_storage_guard_decorator_refuses_below_floor(settings, monkeypatch):
    """STORAGE_PAUSE_PCT=1 -> the wrapped task returns "paused: low disk" and never runs."""
    settings.STORAGE_PAUSE_PCT = 1
    settings.STORAGE_GUARD_ENABLED = True
    _set_usage(monkeypatch, 50)
    calls = []

    @storage.storage_guard
    def fake_task(limit=10):
        calls.append(limit)
        return {"downloaded": limit}

    result = fake_task(limit=10)
    assert result["paused"] is True
    assert "low disk" in result["reason"]
    assert calls == []


@pytest.mark.django_db
def test_storage_guard_decorator_fires_disk_low_notification(settings, monkeypatch):
    """Phase 33 wiring: a refused task also fires the disk_low event."""
    settings.STORAGE_PAUSE_PCT = 1
    settings.STORAGE_GUARD_ENABLED = True
    _set_usage(monkeypatch, 50)

    @storage.storage_guard
    def fake_task(limit=10):
        return {"downloaded": limit}

    with patch("core.notify.send") as send:
        fake_task(limit=10)
    send.assert_called_once()
    assert send.call_args.args[0] == "disk_low"


@pytest.mark.django_db
def test_storage_guard_decorator_passthrough_when_disabled(settings, monkeypatch):
    """Flag off -> behavior identical to today, even over the pause threshold."""
    settings.STORAGE_PAUSE_PCT = 1
    settings.STORAGE_GUARD_ENABLED = False
    _set_usage(monkeypatch, 50)

    @storage.storage_guard
    def fake_task(limit=10):
        return {"downloaded": limit}

    assert fake_task(limit=10) == {"downloaded": 10}


@pytest.mark.django_db
def test_storage_guard_decorator_runs_normally_below_threshold(settings, monkeypatch):
    """Guard on, real usage below threshold -> the task runs exactly as before."""
    settings.STORAGE_PAUSE_PCT = 95
    settings.STORAGE_GUARD_ENABLED = True
    _set_usage(monkeypatch, 10)

    @storage.storage_guard
    def fake_task(limit=10):
        return {"downloaded": limit}

    assert fake_task(limit=10) == {"downloaded": 10}


@pytest.mark.django_db
def test_estimated_days_remaining_unknown_without_history(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    assert storage.estimated_days_remaining() == "--"


@pytest.mark.django_db
def test_dashboard_card_shape(monkeypatch):
    from core import dashboard

    _set_usage(monkeypatch, 50)
    card = dashboard.storage_guard()
    assert set(card) == {"enabled", "level", "used_pct", "warn_pct", "pause_pct", "free_gb", "days_remaining"}
