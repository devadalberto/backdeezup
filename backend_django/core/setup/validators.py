"""Setup-wizard validators (Phase 29).

Reuses the Phase 24 health checks unchanged (core.health) and adds three
wizard-only checks that need the current request: TLS reachability, the OAuth
client file's presence, and whether its registered redirect URI matches this
host. Every check is wrapped so one failure never breaks the page.
"""
import json
import os

from django.urls import reverse

from core import health
from core.errors import humanize_error
from google_media_backup.services_google import CLIENT_SECRETS

OK, WARN, FAIL = health.OK, health.WARN, health.FAIL


def _reuse(check_fn):
    """Adapt a Phase 24 check (no args) to this module's request-taking signature."""
    return lambda request: check_fn()


def check_tls(request):
    if request.is_secure() or request.META.get("HTTP_X_FORWARDED_PROTO") == "https":
        return OK, "Request arrived over HTTPS."
    return WARN, "Request arrived over plain HTTP. Fine for local setup; Google OAuth requires HTTPS in production."


def check_oauth_client(request):
    if not os.path.exists(CLIENT_SECRETS):
        return FAIL, f"No client secrets file at {CLIENT_SECRETS}. Download it from Google Cloud Console."
    return OK, f"Found {CLIENT_SECRETS}"


def check_redirect_uri(request):
    if not os.path.exists(CLIENT_SECRETS):
        return WARN, "Cannot check -- no client secrets file (see the check above)."
    try:
        with open(CLIENT_SECRETS) as f:
            data = json.load(f)
        client_type = next(iter(data))
        registered = data[client_type].get("redirect_uris", [])
    except Exception as exc:
        info = humanize_error(exc)
        return FAIL, f"{info['title']} -- {info['hint']}"
    this_uri = request.build_absolute_uri(reverse("oauth_callback"))
    if this_uri in registered:
        return OK, f"{this_uri} is registered."
    info = humanize_error("redirect_uri_mismatch")
    return WARN, f"{this_uri} is not in the registered redirect_uris. {info['hint']}"


CHECKS = [
    ("database", "Database", _reuse(health.check_database)),
    ("redis", "Redis", _reuse(health.check_redis)),
    ("celery_worker", "Celery worker", _reuse(health.check_celery_worker)),
    ("media_write", "Media write test", _reuse(health.check_media_write)),
    ("storage", "Disk space", _reuse(health.check_storage)),
    ("tls", "TLS reachable", check_tls),
    ("oauth_client", "OAuth client file present", check_oauth_client),
    ("redirect_uri", "Redirect URI matches request host", check_redirect_uri),
]


def run_checks(request):
    results = []
    for key, label, fn in CHECKS:
        try:
            status, detail = fn(request)
        except Exception as exc:
            info = humanize_error(exc)
            status, detail = FAIL, f"{info['title']} -- {info['hint']}"
        results.append({"key": key, "label": label, "status": status, "detail": detail})
    return results


def can_continue(results):
    """FAIL blocks continuing; WARN (e.g. plain HTTP in dev) does not."""
    return not any(r["status"] == FAIL for r in results)
