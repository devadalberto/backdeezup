# backend_django/google_media_backup/admin_views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.shortcuts import render
from .models import DriveAsset, RunLog, MediaItem

@staff_member_required
def reports_view(request):
    by_state = (
        DriveAsset.objects.values("state")
        .annotate(n=Count("id"), bytes=Sum("size_bytes"))
        .order_by("state")
    )
    top_mimes = (
        DriveAsset.objects.values("mime_type")
        .annotate(n=Count("id"))
        .order_by("-n")[:12]
    )
    totals = {
        "assets": DriveAsset.objects.count(),
        "media_items": MediaItem.objects.count(),
        "bytes_total": DriveAsset.objects.aggregate(s=Sum("size_bytes"))["s"] or 0,
    }
    runs = RunLog.objects.order_by("-started_at")[:20]

    ctx = {
        "title": "Reports",
        "summary": by_state,
        "top_mimes": top_mimes,
        "totals": totals,
        "runs": runs,
    }
    return render(request, "admin/reports.html", ctx)


@staff_member_required
def ops_console(request):
    """
    Minimal admin 'Operations Console' that calls your /api/* endpoints
    with a shared 'limit' and shows raw results.
    """
    return render(request, "admin/ops_console.html", {"title": "Operations Console"})
