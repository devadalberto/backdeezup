from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from google_media_backup.api import api
from google_media_backup.views import query_page
from google_media_backup.admin_ops import admin_ops_view  # admin ops page

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin/ops/', admin.site.admin_view(admin_ops_view), name='gmb_ops'),
    path('api/', api.urls),
    path('', query_page, name='query'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
