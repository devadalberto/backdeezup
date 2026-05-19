from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render

from .models import CleanupRule, GmailMessage, GmailSyncState


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
def gmail_rule_builder(request):
    return render(request, "admin/gmail/rule_builder.html", {"title": "Rule Builder"})


@staff_member_required
def gmail_ops(request):
    from .models import CleanupAuditLog, ProtectedSender
    accounts = GmailSyncState.objects.all()
    rules = CleanupRule.objects.all().order_by("name")
    audit_log = CleanupAuditLog.objects.order_by("-started_at")[:20]
    protected_senders = ProtectedSender.objects.all().order_by("email")
    ctx = {
        "title": "Gmail Operations",
        "accounts": accounts,
        "rules": rules,
        "audit_log": audit_log,
        "protected_senders": protected_senders,
    }
    return render(request, "admin/gmail/ops.html", ctx)
