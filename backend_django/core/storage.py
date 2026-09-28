"""Storage guard (Phase 32): disk usage helpers + a pre-check wrapper for
download tasks. Read-only measurement -- the only side effect is refusing to
start a task (or a dashboard action) when free space is at/above the pause
floor. STORAGE_GUARD_ENABLED=False restores today's behavior (no refusals).
"""
import functools
import logging
import os
import shutil
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

OK, WARN, PAUSE = "ok", "warn", "pause"

#: window used by estimated_days_remaining() to average recent downloads.
GROWTH_WINDOW_DAYS = 30


def usage():
    """{"total", "used", "free"} in bytes, plus "used_pct"."""
    # Docker's named volume mount auto-creates MEDIA_ROOT before any file is
    # ever written -- a bare (non-Docker) run has no such guarantee.
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    du = shutil.disk_usage(settings.MEDIA_ROOT)
    used_pct = du.used / du.total * 100 if du.total else 0.0
    return {"total": du.total, "used": du.used, "free": du.free, "used_pct": used_pct}


def free_gb():
    return usage()["free"] / 1024 ** 3


def _avg_item_bytes():
    """Average size of a recently-downloaded item, from whichever source has data."""
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    sizes = list(
        DriveAsset.objects.exclude(size_bytes=0).order_by("-discovered_at").values_list("size_bytes", flat=True)[:500]
    )
    sizes += list(
        GmailMessage.objects.exclude(size_estimate=0).order_by("-discovered_at").values_list("size_estimate", flat=True)[:500]
    )
    if not sizes:
        return None
    return sum(sizes) / len(sizes)


def _avg_daily_growth_bytes():
    """Estimate = (avg item size) x (items downloaded / day), both measured
    over the trailing GROWTH_WINDOW_DAYS from RunLog.totals["downloaded"].
    None when there isn't enough history to estimate.
    """
    from google_media_backup.models import RunLog

    window_start = timezone.now() - timedelta(days=GROWTH_WINDOW_DAYS)
    runs = list(RunLog.objects.filter(started_at__gte=window_start))
    downloaded_items = sum(
        (r.totals or {}).get("downloaded", 0) for r in runs
        if isinstance((r.totals or {}).get("downloaded"), int)
    )
    if downloaded_items <= 0 or not runs:
        return None
    avg_item_bytes = _avg_item_bytes()
    if not avg_item_bytes:
        return None
    earliest = min(r.started_at for r in runs)
    span_days = max((timezone.now() - earliest).total_seconds() / 86400, 1)
    return (downloaded_items * avg_item_bytes) / span_days


def estimated_days_remaining():
    """"--" when there isn't enough history to estimate."""
    growth = _avg_daily_growth_bytes()
    if not growth:
        return "--"
    return round(usage()["free"] / growth, 1)


def is_guard_enabled():
    return getattr(settings, "STORAGE_GUARD_ENABLED", True)


def status():
    """(level, used_pct) -- level is one of ok / warn / pause."""
    pct = usage()["used_pct"]
    if pct >= settings.STORAGE_PAUSE_PCT:
        return PAUSE, pct
    if pct >= settings.STORAGE_WARN_PCT:
        return WARN, pct
    return OK, pct


def guard_block_reason():
    """None when it's fine to proceed, else a human-readable reason to refuse.
    Always None when STORAGE_GUARD_ENABLED is False.
    """
    if not is_guard_enabled():
        return None
    level, pct = status()
    if level == PAUSE:
        return f"low disk: {pct:.1f}% used (>= {settings.STORAGE_PAUSE_PCT}% pause threshold)"
    return None


def storage_guard(func):
    """Decorator for download tasks: a pre-check only, the task body is never
    touched. Refuses to start below the free-space floor and returns early
    with a logged reason instead of running the wrapped function.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        reason = guard_block_reason()
        if reason:
            log.warning("%s: refusing to start -- %s", func.__name__, reason)
            try:
                from core import notify
                notify.send("disk_low", "Storage guard paused a backup task", reason)
            except Exception:
                pass
            return {"paused": True, "reason": reason}
        return func(*args, **kwargs)
    return wrapper


def banner():
    """Dashboard / health banner context: level, thresholds, and the estimate."""
    level, pct = status()
    return {
        "enabled": is_guard_enabled(),
        "level": level,
        "used_pct": round(pct, 1),
        "warn_pct": settings.STORAGE_WARN_PCT,
        "pause_pct": settings.STORAGE_PAUSE_PCT,
        "free_gb": round(free_gb(), 1),
        "days_remaining": estimated_days_remaining(),
    }
