# backend_django/config/urls.py
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import csrf_exempt

# API (Ninja)
from google_media_backup.api import api

# Wagtail
from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

# Landing page
from core.views import (
    landing_page, htmx_stats, health_page, health_json,
    dashboard_page, dashboard_cards, dashboard_action,
    dashboard_connect, dashboard_connect_start, dashboard_disconnect,
    dashboard_verification, dashboard_export, dashboard_export_status,
)

# Setup wizard (Phase 29 welcome/admin; Phase 30 services/connect/storage/schedule/test)
from core.setup.views import (
    setup_welcome, setup_admin, setup_services,
    setup_connect, setup_connect_start, setup_storage, setup_schedule, setup_test,
)

# Optional query page
try:
    from google_media_backup.views import query_page
    HAS_QUERY_PAGE = True
except Exception:
    HAS_QUERY_PAGE = False

# Admin custom pages — Drive/Photos
from google_media_backup.admin_views import reports_view, ops_console

# Admin custom pages — Gmail
from google_gmail_backup.admin_views import gmail_dashboard, gmail_ops, gmail_rule_builder
from google_gmail_backup.htmx_views import htmx_audit_log, htmx_cleanup_status, htmx_gmail_progress

# Gmail API
from google_gmail_backup.api import gmail_api

# Media Vault API + views
from media_vault.api import vault_api
from media_vault.views import review_view, vault_ops

urlpatterns = [
    # Landing page
    path("", landing_page, name="landing"),
    path("htmx/stats/", htmx_stats, name="htmx_stats"),

    # Unified dashboard (staff only, read-only)
    path("dashboard/", dashboard_page, name="dashboard"),
    path("dashboard/cards/", dashboard_cards, name="dashboard_cards"),
    path("dashboard/actions/<slug:name>/", dashboard_action, name="dashboard_action"),
    path("dashboard/connect/", dashboard_connect, name="dashboard_connect"),
    path("dashboard/connect/start/", dashboard_connect_start, name="dashboard_connect_start"),
    path("dashboard/disconnect/", dashboard_disconnect, name="dashboard_disconnect"),
    path("dashboard/verification/", dashboard_verification, name="dashboard_verification"),
    path("dashboard/export/", dashboard_export, name="dashboard_export"),
    path("dashboard/export/<int:job_id>/", dashboard_export_status, name="dashboard_export_status"),

    # Setup wizard -- reachable only on first run, see core.models.is_first_run
    path("setup/", setup_welcome, name="setup_welcome"),
    path("setup/admin/", setup_admin, name="setup_admin"),
    path("setup/services/", setup_services, name="setup_services"),
    path("setup/connect/", setup_connect, name="setup_connect"),
    path("setup/connect/start/", setup_connect_start, name="setup_connect_start"),
    path("setup/storage/", setup_storage, name="setup_storage"),
    path("setup/schedule/", setup_schedule, name="setup_schedule"),
    path("setup/test/", setup_test, name="setup_test"),

    # System health (staff only, read-only)
    path("health/", health_page, name="health"),
    path("health/json/", health_json, name="health_json"),

    # Drive/Photos admin dashboards
    path("admin/reports/", reports_view, name="admin_reports"),
    path("admin/ops/", ops_console, name="admin_ops"),

    # Gmail admin dashboards
    path("admin/gmail/dashboard/", gmail_dashboard, name="admin_gmail_dashboard"),
    path("admin/gmail/ops/", gmail_ops, name="admin_gmail_ops"),
    path("admin/gmail/rule-builder/", gmail_rule_builder, name="admin_gmail_rule_builder"),
    path("htmx/gmail/cleanup-status/", htmx_cleanup_status, name="htmx_cleanup_status"),
    path("htmx/gmail/audit-log/", htmx_audit_log, name="htmx_audit_log"),
    path("htmx/gmail/progress/", htmx_gmail_progress, name="htmx_gmail_progress"),

    # Django admin
    path("admin/", admin.site.urls),

    # Drive/Photos Ninja API
    path("api/", api.urls),

    # Gmail Ninja API
    path("api/gmail/", gmail_api.urls),

    # Media Vault API + review UI + ops
    path("api/vault/", vault_api.urls),
    path("vault/review/", review_view, name="vault_review"),
    path("admin/vault/ops/", vault_ops, name="vault_ops"),
]

if HAS_QUERY_PAGE:
    urlpatterns += [path("", query_page, name="query")]

# OAuth callback — CSRF exempt because OAuth providers cannot set CSRF tokens.
# Two paths land here:
#  - CLI (`make auth`): the browser hits this URL only so the human can copy it from the
#    address bar; nothing here processes it. That behavior is unchanged (Phase 28).
#  - Browser (Phase 28 /dashboard/connect/, Phase 30 /setup/connect/): the session holds
#    a matching, unexpired state -- core.oauth.is_our_callback() -- so this view completes
#    the flow itself and returns to whichever page called core.oauth.start().
@csrf_exempt
def oauth_callback(request):
    from core.oauth import handle_callback, is_our_callback, pop_return_to

    if is_our_callback(request):
        ok, message = handle_callback(request)
        request.session["oauth_result"] = {"ok": ok, "message": message}
        return redirect(pop_return_to(request))
    return HttpResponse(
        "<h2>OAuth completed.</h2><p>You can close this tab and return to the terminal.</p>",
        status=200,
    )

urlpatterns += [path("api/oauth/callback", oauth_callback, name="oauth_callback")]

urlpatterns += [
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("vault/", include(wagtail_urls)),
]

# Media files — dev only. In production nginx serves MEDIA_ROOT directly.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
