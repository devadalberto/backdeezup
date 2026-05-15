from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render

from .models import GmailMessage, GmailSyncState


@staff_member_required
def gmail_dashboard(request):
    accounts = GmailSyncState.objects.all()
    by_state = (
        GmailMessage.objects.values("state")
        .annotate(n=Count("id"), bytes=Sum("size_estimate"))
        .order_by("state")
    )
    top_senders = (
        GmailMessage.objects.values("from_address")
        .annotate(n=Count("id"), bytes=Sum("size_estimate"))
        .order_by("-n")[:20]
    )
    totals = {
        "messages": GmailMessage.objects.count(),
        "downloaded": GmailMessage.objects.filter(state=GmailMessage.STATE_DOWNLOADED).count(),
        "verified": GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count(),
        "with_attachments": GmailMessage.objects.filter(has_attachments=True).count(),
        "bytes_total": GmailMessage.objects.aggregate(s=Sum("size_estimate"))["s"] or 0,
    }
    ctx = {
        "title": "Gmail Dashboard",
        "accounts": accounts,
        "by_state": by_state,
        "top_senders": top_senders,
        "totals": totals,
    }
    return render(request, "admin/gmail/dashboard.html", ctx)


@staff_member_required
def gmail_ops(request):
    accounts = GmailSyncState.objects.all()
    ctx = {
        "title": "Gmail Operations",
        "accounts": accounts,
    }
    return render(request, "admin/gmail/ops.html", ctx)
