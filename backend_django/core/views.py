import logging
import os
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

log = logging.getLogger(__name__)


def landing_page(request):
    return render(request, "core/landing.html")


@require_GET
def htmx_stats(request):
    """HTMX partial — returns live stats cards. Polled every 10s."""
    from google_media_backup.models import DriveAsset, MediaItem
    from google_gmail_backup.models import GmailMessage, CleanupAuditLog, GmailSyncState

    try:
        from django.db.models import Sum
        drive_total = DriveAsset.objects.count()
        drive_verified = DriveAsset.objects.filter(state="VERIFIED").count()
        drive_pct = round(drive_verified / max(drive_total, 1) * 100)

        gmail_total = GmailSyncState.objects.aggregate(t=Sum('total_messages'))['t'] or 0
        gmail_verified = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count()
        gmail_pct = round(gmail_verified / max(gmail_total, 1) * 100)

        media_items = MediaItem.objects.count()

        from media_vault.models import VaultImage, VaultMedia
        vault_images = VaultImage.objects.count()
        vault_media = VaultMedia.objects.count()

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
            "vault_images": vault_images,
            "vault_media": vault_media,
            "running_job": running_job,
            "last_cleanup": last_cleanup,
        }
    except Exception as e:
        log.warning("htmx_stats error: %s", e)
        ctx = {}

    return render(request, "core/partials/stats.html", ctx)


def _staff_only(view):
    """Staff-only: the page redirects to the admin login, the JSON endpoint answers 403."""
    from django.contrib.admin.views.decorators import staff_member_required

    return staff_member_required(view, login_url="admin:login")


@_staff_only
@require_GET
def health_page(request):
    """System health page (Phase 24). Read-only; always 200 even when checks fail."""
    from core.health import overall_status, run_checks
    from core.storage import banner as storage_banner

    results = run_checks()
    return render(request, "core/health.html", {
        "checks": results,
        "overall": overall_status(results),
        "storage_guard": storage_banner(),
    })


@require_GET
def health_json(request):
    from django.http import JsonResponse
    from core.health import overall_status, run_checks
    from core.storage import banner as storage_banner

    if not (request.user.is_active and request.user.is_staff):
        return JsonResponse({"detail": "Staff only"}, status=403)
    results = run_checks()
    return JsonResponse({
        "status": overall_status(results),
        "checks": results,
        "storage_guard": storage_banner(),
    })


@_staff_only
@require_GET
def dashboard_page(request):
    """Unified dashboard shell (Phase 25). Cards load via HTMX and refresh every 30s."""
    return render(request, "core/dashboard.html")


@_staff_only
@require_GET
def dashboard_cards(request):
    """HTMX partial: the DB-backed dashboard cards."""
    from core.dashboard import build_cards

    return render(request, "core/partials/dashboard_cards.html", build_cards())


@_staff_only
@require_POST
def dashboard_action(request, name):
    """POST-only: enqueue an existing Celery task (staff + CSRF, see core.actions)."""
    from django.http import JsonResponse
    from core.actions import run_action
    from core.errors import humanize_error

    try:
        status, payload = run_action(name)
    except Exception as exc:  # broker / cache down
        info = humanize_error(exc)
        status, payload = 503, {"ok": False, "message": f"{info['title']} -- {info['hint']}"}
    if request.headers.get("HX-Request"):
        return render(request, "core/partials/action_result.html", payload, status=200)
    return JsonResponse(payload, status=status)


@_staff_only
@require_GET
def dashboard_connect(request):
    """Browser OAuth connect page (Phase 28): scopes, status, Reconnect/Disconnect."""
    from core.oauth import scope_list, status as oauth_status

    result = request.session.pop("oauth_result", None)
    return render(request, "core/connect.html", {
        "scopes": scope_list(),
        "connection": oauth_status(),
        "result": result,
    })


@_staff_only
@require_POST
def dashboard_connect_start(request):
    """Redirects to Google's consent screen. POST-only + CSRF (this is state-changing: it
    starts a new OAuth session and, on Reconnect, will replace the saved token)."""
    from core.errors import humanize_error
    from core.oauth import start

    try:
        return redirect(start(request))
    except Exception as exc:
        info = humanize_error(exc)
        request.session["oauth_result"] = {"ok": False, "message": f"{info['title']} -- {info['hint']}"}
        return redirect("dashboard_connect")


@_staff_only
@require_GET
def dashboard_verification(request):
    """Verification report (Phase 31): backed-up counts, missing files, oldest
    verified, and the latest sampled integrity check. Read-only."""
    from core.verification import build_report

    return render(request, "core/verification.html", build_report())


@_staff_only
@require_POST
def dashboard_export(request):
    """Phase 36 -- export backed-up files to ZIP/TAR. scope=source|everything
    (scope=selection is only exposed via the admin "Export selected" actions,
    see google_gmail_backup/admin.py and google_media_backup/admin.py).
    Small results stream straight through; large ones (or scope=everything)
    run as a Celery task writing to MEDIA_ROOT/exports/.
    """
    from django.http import JsonResponse, StreamingHttpResponse
    from django.shortcuts import render

    from core.export import (
        archive_content_type, archive_filename, async_item_threshold,
        iter_archive_stream, resolve_export_items,
    )

    fmt = request.POST.get("format", "zip").lower()
    scope = request.POST.get("scope", "").lower()
    source = request.POST.get("source") or None
    is_ui = request.POST.get("ui") == "1"

    def _error(message, status=400):
        if is_ui:
            return render(request, "core/export_status.html", {"error": message}, status=status)
        return JsonResponse({"ok": False, "message": message}, status=status)

    if fmt not in ("zip", "tar"):
        return _error("format must be 'zip' or 'tar'.")
    if scope not in ("source", "everything"):
        return _error("scope must be 'source' or 'everything'.")

    try:
        items = resolve_export_items(scope, source=source)
    except ValueError as exc:
        return _error(str(exc))

    if not items:
        return _error("Nothing to export -- no backed-up files matched.", status=404)

    if scope == "everything" or len(items) > async_item_threshold():
        from core.models import ExportJob
        from core.tasks import task_run_export

        job = ExportJob.objects.create(
            scope=scope, source=source or "", format=fmt, item_count=len(items),
            item_ids={
                "gmail": [i["db_id"] for i in items if i["kind"] == "gmail"],
                "media": [i["db_id"] for i in items if i["kind"] == "media"],
            },
        )
        task_run_export.delay(job.id)
        if is_ui:
            return render(request, "core/export_status.html", {"job": job})
        return JsonResponse({
            "ok": True, "async": True, "job_id": job.id, "item_count": len(items),
            "status_url": f"/dashboard/export/{job.id}/",
        })

    resp = StreamingHttpResponse(iter_archive_stream(items, fmt), content_type=archive_content_type(fmt))
    resp["Content-Disposition"] = f'attachment; filename="{archive_filename(scope, fmt)}"'
    return resp


@_staff_only
@require_GET
def dashboard_export_status(request, job_id):
    """Phase 36 -- poll/download an async export job."""
    from django.http import FileResponse, Http404, JsonResponse

    from core.models import ExportJob

    job = ExportJob.objects.filter(pk=job_id).first()
    if job is None:
        raise Http404("No such export job.")

    if request.GET.get("download") and job.status == ExportJob.Status.DONE:
        if not job.file_path or not os.path.exists(job.file_path):
            return JsonResponse({"ok": False, "message": "Export file no longer exists on disk."}, status=404)
        return FileResponse(open(job.file_path, "rb"), as_attachment=True, filename=os.path.basename(job.file_path))

    if request.headers.get("HX-Request") or request.GET.get("ui") == "1":
        from django.shortcuts import render
        return render(request, "core/partials/export_status.html", {"job": job})

    return JsonResponse({
        "job_id": job.id, "scope": job.scope, "source": job.source, "format": job.format,
        "status": job.status, "item_count": job.item_count, "error": job.error,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "download_url": f"/dashboard/export/{job.id}/?download=1" if job.status == ExportJob.Status.DONE else None,
    })


@_staff_only
@require_POST
def dashboard_disconnect(request):
    """Deletes the stored token after an explicit confirm. Never touches backed-up data."""
    from core.oauth import disconnect

    removed = disconnect()
    request.session["oauth_result"] = {
        "ok": True,
        "message": "Google account disconnected." if removed else "No token was stored.",
    }
    return redirect("dashboard_connect")
