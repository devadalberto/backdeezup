# backend_django/config/urls.py
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

# API (Ninja)
from google_media_backup.api import api

# Optional landing view (keep if you have it)
try:
    from google_media_backup.views import query_page
    HAS_QUERY_PAGE = True
except Exception:
    HAS_QUERY_PAGE = False

# Admin custom pages — Drive/Photos
from google_media_backup.admin_views import reports_view, ops_console

# Admin custom pages — Gmail
from google_gmail_backup.admin_views import gmail_dashboard, gmail_ops

# Gmail API
from google_gmail_backup.api import gmail_api

urlpatterns = [
    # Drive/Photos admin dashboards
    path("admin/reports/", reports_view, name="admin_reports"),
    path("admin/ops/", ops_console, name="admin_ops"),

    # Gmail admin dashboards
    path("admin/gmail/dashboard/", gmail_dashboard, name="admin_gmail_dashboard"),
    path("admin/gmail/ops/", gmail_ops, name="admin_gmail_ops"),

    # Django admin
    path("admin/", admin.site.urls),

    # Drive/Photos Ninja API
    path("api/", api.urls),

    # Gmail Ninja API
    path("api/gmail/", gmail_api.urls),
]

if HAS_QUERY_PAGE:
    urlpatterns += [path("", query_page, name="query")]

# OAuth callback — web client type redirects here; returns 200 so browser shows success
from django.http import HttpResponse

def oauth_callback(request):
    return HttpResponse(
        "<h2>OAuth completed.</h2><p>You can close this tab and return to the terminal.</p>",
        status=200,
    )

urlpatterns += [path("api/oauth/callback", oauth_callback, name="oauth_callback")]

# Static/media (dev)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
