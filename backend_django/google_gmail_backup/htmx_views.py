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
    """Gmail pipeline progress bar fragment."""
    from .models import GmailMessage, GmailSyncState
    from django.db.models import Sum

    sync_total = GmailSyncState.objects.aggregate(t=Sum("total_messages"))["t"] or 0
    verified = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count()
    discovered = GmailMessage.objects.filter(state=GmailMessage.STATE_DISCOVERED).count()
    pct = round(verified / max(sync_total, 1) * 100, 1)
    filled = int(pct / 5)
    bar = "=" * filled + "-" * (20 - filled)

    ctx = {
        "sync_total": sync_total,
        "verified": verified,
        "discovered": discovered,
        "pct": pct,
        "bar": bar,
    }
    return render(request, "admin/gmail/partials/gmail_progress.html", ctx)
