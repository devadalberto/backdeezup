"""Unified dashboard card data (Phase 25). Read-only.

Every number is a DB query (or a disk measurement) -- nothing is invented. Each
card builder is isolated: one failing never blanks the others, it degrades to
``{"error": <humanized text>}``.
"""
import shutil
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone

from core.errors import humanize_error
from core.labels import item_label

RECENT_ERRORS = 8
ERROR_WINDOW = timedelta(days=7)


def _fmt_bytes(n):
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    return f"{n / 1024 ** 2:.0f} MB"


def _fmt_duration(delta):
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s"
    if secs < 3600:
        return f"{secs // 60}m {secs % 60}s"
    return f"{secs // 3600}h {secs % 3600 // 60}m"


def backup_status():
    from google_media_backup.models import RunLog

    latest = RunLog.objects.order_by("-started_at").first()
    last_ok = RunLog.objects.filter(status="OK", finished_at__isnull=False).order_by("-finished_at").first()
    return {
        "running": RunLog.objects.filter(status="RUNNING").count(),
        "latest_status": latest.status if latest else None,
        "latest_at": latest.started_at if latest else None,
        "last_ok_at": last_ok.finished_at if last_ok else None,
        "last_ok_duration": _fmt_duration(last_ok.finished_at - last_ok.started_at) if last_ok else None,
    }


def items_per_source():
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset
    from media_vault.models import VaultImage, VaultMedia

    return {
        "drive": DriveAsset.objects.count(),
        "gmail": GmailMessage.objects.count(),
        "vault_images": VaultImage.objects.count(),
        "vault_media": VaultMedia.objects.count(),
    }


def verified_counts():
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    drive = DriveAsset.objects.filter(state=DriveAsset.State.VERIFIED).count()
    gmail = GmailMessage.objects.filter(state=GmailMessage.State.VERIFIED).count()
    return {"drive": drive, "gmail": gmail, "total": drive + gmail}


def storage():
    usage = shutil.disk_usage(settings.MEDIA_ROOT)
    return {
        "used": _fmt_bytes(usage.used),
        "free": _fmt_bytes(usage.free),
        "total": _fmt_bytes(usage.total),
        "used_pct": round(usage.used / max(usage.total, 1) * 100, 1),
    }


def recent_errors():
    from google_gmail_backup.models import CleanupAuditLog, GmailSyncState
    from google_media_backup.models import RunLog

    since = timezone.now() - ERROR_WINDOW
    found = []  # (when, source, raw text)
    for run in RunLog.objects.filter(started_at__gte=since).exclude(error_log=[]).order_by("-started_at")[:RECENT_ERRORS]:
        for entry in (run.error_log or [])[:1]:
            text = entry.get("error", "") if isinstance(entry, dict) else str(entry)
            found.append((run.started_at, "Drive/Media run", text))
    for st in GmailSyncState.objects.filter(last_error_at__gte=since).exclude(last_error=""):
        found.append((st.last_error_at, f"Gmail sync ({st.email})", st.last_error))
    for log in CleanupAuditLog.objects.filter(started_at__gte=since).exclude(error_text="").order_by("-started_at")[:RECENT_ERRORS]:
        found.append((log.started_at, f"Cleanup ({log.rule_name})", log.error_text))
    found.sort(key=lambda t: t[0], reverse=True)
    rows = []
    for when, source, text in found[:RECENT_ERRORS]:
        info = humanize_error(text)
        rows.append({"when": when, "source": source, "title": info["title"], "hint": info["hint"], "code": info["code"]})
    return {"rows": rows, "window_days": ERROR_WINDOW.days}


def next_run():
    from django_celery_beat.models import PeriodicTask

    now = timezone.now()
    best = None
    for pt in PeriodicTask.objects.filter(enabled=True).exclude(task="celery.backend_cleanup"):
        try:
            _due, secs = pt.schedule.is_due(pt.last_run_at or now)
        except Exception:
            continue
        when = now + timedelta(seconds=max(secs, 0))
        if best is None or when < best[0]:
            best = (when, pt.name)
    return {"when": best[0], "name": best[1]} if best else None


def connection():
    from core.health import check_oauth
    from google_gmail_backup.models import GmailSyncState

    status, detail = check_oauth()
    return {
        "status": status,
        "detail": detail,
        "accounts": list(GmailSyncState.objects.order_by("email").values_list("email", flat=True)),
    }


def storage_guard():
    from core.storage import banner

    return banner()


def cleanup_state():
    from google_gmail_backup.models import CleanupAuditLog, CleanupRule

    agg = CleanupRule.objects.aggregate(total=Count("id"), last=Max("last_run_at"))
    enabled = CleanupRule.objects.filter(enabled=True).count()
    return {
        "enabled": enabled,
        "disabled": agg["total"] - enabled,
        "last_run_at": agg["last"],
        "running": CleanupAuditLog.objects.filter(status="RUNNING").count(),
    }


def run_progress():
    """Latest RunLog: done / skipped / failed and, only if computable, an ETA."""
    from google_media_backup.models import DriveAsset, RunLog
    from core.actions import is_paused

    run = RunLog.objects.order_by("-started_at").first()
    out = {"paused": is_paused(), "run": None}
    if run is None:
        return out
    totals = run.totals or {}
    done = sum(v for v in totals.values() if isinstance(v, int))
    eta = None
    if run.status == "RUNNING":
        elapsed = (timezone.now() - run.started_at).total_seconds()
        downloaded = totals.get("downloaded", 0)
        remaining = DriveAsset.objects.filter(state=DriveAsset.State.DISCOVERED).count()
        if elapsed > 0 and downloaded > 0 and remaining > 0:
            eta = _fmt_duration(timedelta(seconds=remaining / (downloaded / elapsed)))
    out["run"] = {
        "status": run.status,
        "started_at": run.started_at,
        "done": done,
        "skipped": totals.get("skipped"),
        "failed": len(run.error_log or []),
        "eta": eta,
    }
    return out


def recent_items(per_source=5):
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    rows = []
    for a in DriveAsset.objects.order_by("-discovered_at")[:per_source]:
        source = "Photos" if a.drive_id.startswith("photos:") else "Drive"
        rows.append({"when": a.discovered_at, "source": source, "name": a.name, "chip": item_label(a)})
    for m in GmailMessage.objects.order_by("-discovered_at")[:per_source]:
        rows.append({"when": m.discovered_at, "source": "Gmail", "name": m.subject or "(no subject)", "chip": item_label(m)})
    rows.sort(key=lambda r: r["when"], reverse=True)
    return {"rows": rows}


CARDS = [
    ("backup", backup_status),
    ("sources", items_per_source),
    ("verified", verified_counts),
    ("storage", storage),
    ("progress", run_progress),
    ("items", recent_items),
    ("errors", recent_errors),
    ("next_run", next_run),
    ("connection", connection),
    ("cleanup", cleanup_state),
    ("storage_guard", storage_guard),
]


def build_cards():
    ctx = {}
    for key, fn in CARDS:
        try:
            ctx[key] = fn()
        except Exception as exc:
            info = humanize_error(exc)
            ctx[key] = {"error": f"{info['title']} -- {info['hint']}"}
    return ctx
