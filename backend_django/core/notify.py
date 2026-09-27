"""Notifications (Phase 33): fan an event out to whichever channels are
configured. Every channel is off unless its env var is set. A channel failure
is logged and swallowed -- ``send()`` never raises into the caller's task or
view. Duplicate events are rate-limited to once per hour via a Redis SETNX
(``cache.add``), same mechanism as the existing Celery task locks.
"""
import logging

import requests
from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)

DEDUP_TTL_SECONDS = 3600
TIMEOUT_SECONDS = 5


def _dedup_key(event):
    return f"backdeezup:notify:{event}"


def _already_sent_this_hour(event):
    """True (and the caller should skip) if this event key fired within the window."""
    try:
        return not cache.add(_dedup_key(event), "1", DEDUP_TTL_SECONDS)
    except Exception:
        return False  # fail open -- don't swallow a notification because the cache is down


def _send_webhook(url, event, title, body):
    requests.post(url, json={"event": event, "title": title, "body": body}, timeout=TIMEOUT_SECONDS)


def _send_slack(url, event, title, body):
    requests.post(url, json={"text": f"*{title}*\n{body}"}, timeout=TIMEOUT_SECONDS)


def _send_discord(url, event, title, body):
    requests.post(url, json={"content": f"**{title}**\n{body}"}, timeout=TIMEOUT_SECONDS)


def _send_email(recipients, event, title, body):
    from django.core.mail import send_mail

    send_mail(subject=title, message=body, from_email=None, recipient_list=recipients)


def send(event, title, body):
    """Fan ``(event, title, body)`` out to every configured channel.

    Never raises. Returns ``{"sent": bool, "channels": [...]}`` (or
    ``{"sent": False, "reason": "rate_limited"}`` when suppressed).
    """
    if _already_sent_this_hour(event):
        log.info("notify: %s suppressed -- already sent within the last hour", event)
        return {"sent": False, "reason": "rate_limited"}

    channels = []
    for name, fn, target in (
        ("webhook", _send_webhook, getattr(settings, "NOTIFY_WEBHOOK_URL", "")),
        ("slack", _send_slack, getattr(settings, "NOTIFY_SLACK_URL", "")),
        ("discord", _send_discord, getattr(settings, "NOTIFY_DISCORD_URL", "")),
    ):
        if not target:
            continue
        try:
            fn(target, event, title, body)
            channels.append(name)
        except Exception as exc:
            log.warning("notify: %s channel failed for event %s: %s", name, event, exc)

    email_to = [e.strip() for e in getattr(settings, "NOTIFY_EMAIL_TO", "").split(",") if e.strip()]
    if email_to:
        try:
            _send_email(email_to, event, title, body)
            channels.append("email")
        except Exception as exc:
            log.warning("notify: email channel failed for event %s: %s", event, exc)

    if not channels:
        log.debug("notify: %s -- no channel configured, nothing sent", event)
    return {"sent": bool(channels), "channels": channels}
