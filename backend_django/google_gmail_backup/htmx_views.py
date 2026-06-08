"""
HTMX partial views for Gmail ops console.
Returns HTML fragments for live updates without page reload.
"""
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)


@staff_member_required
@require_GET
def htmx_cleanup_status(request):
    """Live cleanup job status — polled by HTMX every 3s when a job is running."""
    from .models import CleanupAuditLog, CleanupRule

    running = CleanupAuditLog.objects.filter(status="RUNNING").order_by("-started_at").first()
    recent = CleanupAuditLog.objects.filter(dry_run=False).order_by("-started_at")[:5]
    enabled_count = CleanupRule.objects.filter(enabled=True).count()
    total_count = CleanupRule.objects.count()

    ctx = {
        "running": running,
        "recent": recent,
        "enabled_count": enabled_count,
        "total_count": total_count,
    }
    return render(request, "admin/gmail/partials/cleanup_status.html", ctx)


@staff_member_required
@require_GET
def htmx_audit_log(request):
    """Latest audit log entries — polled every 10s."""
    from .models import CleanupAuditLog
    logs = CleanupAuditLog.objects.order_by("-started_at")[:20]
    return render(request, "admin/gmail/partials/audit_log.html", {"audit_log": logs})


@staff_member_required
@require_GET
def htmx_gmail_progress(request):
    """Gmail pipeline progress bar fragment — includes disk usage stats."""
    import os
    import shutil
    from .models import GmailMessage, GmailSyncState
    from django.conf import settings
    from django.db.models import Sum

    sync_total = GmailSyncState.objects.aggregate(t=Sum("total_messages"))["t"] or 0
    verified = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count()
    discovered = GmailMessage.objects.filter(state=GmailMessage.STATE_DISCOVERED).count()
    accounted = GmailMessage.objects.filter(
        state__in=[
            GmailMessage.STATE_VERIFIED,
            GmailMessage.STATE_TRASHED,
            GmailMessage.STATE_SOFT_DELETED,
            GmailMessage.STATE_DELETED,
        ]
    ).count()
    pct = round(accounted / max(sync_total, 1) * 100, 1)
    filled = int(pct / 5)
    bar = "=" * filled + "-" * (20 - filled)

    # Disk usage — DISK_USAGE_PATH overrides the volume path reported
    # (Docker on WSL2 may report the host's large virtual disk, not the Windows OS disk)
    from decouple import config as _cfg
    disk_path = _cfg("DISK_USAGE_PATH", default=str(settings.MEDIA_ROOT))
    gmail_dir = os.path.join(settings.MEDIA_ROOT, "gmail")
    disk_total = disk_used = disk_free = gmail_size = 0
    disk_pct = 0
    try:
        disk_total, disk_used, disk_free = shutil.disk_usage(disk_path)
        disk_pct = round(disk_used / max(disk_total, 1) * 100, 1)
        if os.path.exists(gmail_dir):
            gmail_size = sum(
                os.path.getsize(os.path.join(r, f))
                for r, _, files in os.walk(gmail_dir)
                for f in files
            )
    except Exception as exc:
        log.warning("htmx_gmail_progress disk usage error: %s", exc)

    def _fmt(b):
        if b >= 1024 ** 3:
            return f"{b / 1024 ** 3:.1f} GB"
        return f"{b / 1024 ** 2:.0f} MB"

    ctx = {
        "sync_total": sync_total,
        "verified": verified,
        "discovered": discovered,
        "pct": pct,
        "bar": bar,
        "gmail_size": _fmt(gmail_size),
        "disk_used": _fmt(disk_used),
        "disk_total": _fmt(disk_total),
        "disk_free": _fmt(disk_free),
        "disk_pct": disk_pct,
    }
    return render(request, "admin/gmail/partials/gmail_progress.html", ctx)
