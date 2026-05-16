import logging
from django.shortcuts import render
from django.views.decorators.http import require_GET

log = logging.getLogger(__name__)


def landing_page(request):
    return render(request, "core/landing.html")


@require_GET
def htmx_stats(request):
    """HTMX partial — returns live stats cards. Polled every 10s."""
    from google_media_backup.models import DriveAsset, MediaItem
    from google_gmail_backup.models import GmailMessage, CleanupAuditLog, GmailSyncState

    try:
        drive_total = DriveAsset.objects.count()
        drive_verified = DriveAsset.objects.filter(state="VERIFIED").count()
        drive_pct = round(drive_verified / max(drive_total, 1) * 100)

        gmail_total = GmailSyncState.objects.aggregate(t=__import__('django.db.models', fromlist=['Sum']).Sum('total_messages'))['t'] or 0
        gmail_verified = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count()
        gmail_pct = round(gmail_verified / max(gmail_total, 1) * 100)

        media_items = MediaItem.objects.count()

        running_job = CleanupAuditLog.objects.filter(status="RUNNING").order_by("-started_at").first()
        last_cleanup = CleanupAuditLog.objects.filter(status="OK", dry_run=False).order_by("-started_at").first()

        ctx = {
            "drive_total": drive_total,
            "drive_verified": drive_verified,
            "drive_pct": drive_pct,
            "gmail_total": gmail_total,
            "gmail_verified": gmail_verified,
            "gmail_pct": gmail_pct,
            "media_items": media_items,
            "running_job": running_job,
            "last_cleanup": last_cleanup,
        }
    except Exception as e:
        log.warning("htmx_stats error: %s", e)
        ctx = {}

    return render(request, "core/partials/stats.html", ctx)
