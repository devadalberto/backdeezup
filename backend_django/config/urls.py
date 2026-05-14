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

# Admin custom pages
from google_media_backup.admin_views import reports_view, ops_console

urlpatterns = [
    # Admin custom dashboards
    path("admin/reports/", reports_view, name="admin_reports"),
    path("admin/ops/", ops_console, name="admin_ops"),

    # Django admin
    path("admin/", admin.site.urls),

    # Ninja API
    path("api/", api.urls),
]

if HAS_QUERY_PAGE:
    urlpatterns += [path("", query_page, name="query")]

# Static/media (dev)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
