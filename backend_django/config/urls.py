# backend_django/config/urls.py
from django.contrib import admin
from django.http import HttpResponse
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

# Optional landing view (keep if you have it)
try:
    from google_media_backup.views import query_page
    HAS_QUERY_PAGE = True
except Exception:
    HAS_QUERY_PAGE = False

# Admin custom pages — Drive/Photos
from google_media_backup.admin_views import reports_view, ops_console

# Admin custom pages — Gmail
from google_gmail_backup.admin_views import gmail_dashboard, gmail_ops, gmail_rule_builder

# Gmail API
from google_gmail_backup.api import gmail_api

# Media Vault API + views
from media_vault.api import vault_api
from media_vault.views import review_view

urlpatterns = [
    # Drive/Photos admin dashboards
    path("admin/reports/", reports_view, name="admin_reports"),
    path("admin/ops/", ops_console, name="admin_ops"),

    # Gmail admin dashboards
    path("admin/gmail/dashboard/", gmail_dashboard, name="admin_gmail_dashboard"),
    path("admin/gmail/ops/", gmail_ops, name="admin_gmail_ops"),
    path("admin/gmail/rule-builder/", gmail_rule_builder, name="admin_gmail_rule_builder"),

    # Django admin
    path("admin/", admin.site.urls),

    # Drive/Photos Ninja API
    path("api/", api.urls),

    # Gmail Ninja API
    path("api/gmail/", gmail_api.urls),

    # Media Vault API + review UI
    path("api/vault/", vault_api.urls),
    path("vault/review/", review_view, name="vault_review"),
]

if HAS_QUERY_PAGE:
    urlpatterns += [path("", query_page, name="query")]

# OAuth callback — CSRF exempt because OAuth providers cannot set CSRF tokens.
# State parameter validation happens inside start_oauth_local() via PKCE.
@csrf_exempt
def oauth_callback(request):
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
