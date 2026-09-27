"""Phase 33 — notification fan-out tests."""
from unittest.mock import MagicMock, patch

import pytest

from core import notify

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "notify-test"}}


@pytest.fixture(autouse=True)
def local_cache(settings):
    settings.CACHES = LOCMEM
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def no_channels_by_default(settings):
    settings.NOTIFY_WEBHOOK_URL = ""
    settings.NOTIFY_SLACK_URL = ""
    settings.NOTIFY_DISCORD_URL = ""
    settings.NOTIFY_EMAIL_TO = ""


def test_no_channels_configured_sends_nothing():
    result = notify.send("some_event", "title", "body")
    assert result == {"sent": False, "channels": []}


def test_webhook_channel_called_when_configured(settings):
    settings.NOTIFY_WEBHOOK_URL = "https://example.com/hook"
    with patch("core.notify.requests.post") as post:
        result = notify.send("evt", "title", "body")
    assert result["sent"] is True and result["channels"] == ["webhook"]
    post.assert_called_once()
    assert post.call_args.args[0] == "https://example.com/hook"


def test_all_channels_fan_out(settings):
    settings.NOTIFY_WEBHOOK_URL = "https://example.com/hook"
    settings.NOTIFY_SLACK_URL = "https://slack.example.com/hook"
    settings.NOTIFY_DISCORD_URL = "https://discord.example.com/hook"
    settings.NOTIFY_EMAIL_TO = "a@b.c, c@d.e"
    with patch("core.notify.requests.post") as post, patch("core.notify._send_email") as email:
        result = notify.send("evt", "title", "body")
    assert result["sent"] is True
    assert set(result["channels"]) == {"webhook", "slack", "discord", "email"}
    assert post.call_count == 3
    email.assert_called_once_with(["a@b.c", "c@d.e"], "evt", "title", "body")


def test_channel_failure_is_swallowed_and_others_still_run(settings):
    settings.NOTIFY_WEBHOOK_URL = "https://example.com/hook"
    settings.NOTIFY_SLACK_URL = "https://slack.example.com/hook"
    with patch("core.notify.requests.post", side_effect=[Exception("boom"), MagicMock()]) as post:
        result = notify.send("evt", "title", "body")
    assert result["sent"] is True
    assert result["channels"] == ["slack"]
    assert post.call_count == 2


def test_duplicate_events_rate_limited_to_once_per_hour(settings):
    settings.NOTIFY_WEBHOOK_URL = "https://example.com/hook"
    with patch("core.notify.requests.post") as post:
        first = notify.send("evt", "title", "body")
        second = notify.send("evt", "title", "body")
    assert first["sent"] is True
    assert second == {"sent": False, "reason": "rate_limited"}
    post.assert_called_once()


def test_different_events_are_not_rate_limited_together(settings):
    settings.NOTIFY_WEBHOOK_URL = "https://example.com/hook"
    with patch("core.notify.requests.post"):
        a = notify.send("evt_a", "title", "body")
        b = notify.send("evt_b", "title", "body")
    assert a["sent"] is True and b["sent"] is True


def test_dedup_fails_open_when_cache_is_unreachable(settings):
    settings.NOTIFY_WEBHOOK_URL = "https://example.com/hook"
    with patch("core.notify.cache.add", side_effect=ConnectionError("redis down")), \
         patch("core.notify.requests.post") as post:
        result = notify.send("evt", "title", "body")
    assert result["sent"] is True
    post.assert_called_once()
