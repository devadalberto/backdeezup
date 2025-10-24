from django.contrib import admin
from django.conf import settings
from django.urls import reverse
from django.utils.html import format_html
from .models import DriveAsset, MediaItem, RunLog

admin.site.site_header = getattr(settings, 'ADMIN_SITE_HEADER', 'Admin')
admin.site.site_title = getattr(settings, 'ADMIN_SITE_TITLE', 'Admin')
admin.site.index_title = getattr(settings, 'ADMIN_INDEX_TITLE', 'Dashboard')

def ops_link():
    url = reverse('gmb_ops')
    return format_html('<a class="button" href="{}">Open Operations Console</a>', url)

@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ('sha256', 'file', 'created_at')

@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ('run_id', 'status', 'started_at', 'finished_at')

@admin.register(DriveAsset)
class DriveAssetAdmin(admin.ModelAdmin):
    list_display = ('drive_id', 'name', 'mime_type', 'state', 'download_path', 'imported_at')
    list_filter = ('state', 'mime_type')
    search_fields = ('drive_id', 'name')
    actions = ['action_mark_delete', 'action_commit_delete']

    @admin.action(description="Mark selected as DELETE_PENDING")
    def action_mark_delete(self, request, queryset):
        queryset.filter(state='VERIFIED').update(state='DELETE_PENDING')

    @admin.action(description="Commit delete (Drive) [Queue only]")
    def action_commit_delete(self, request, queryset):
        updated = queryset.filter(state='DELETE_PENDING').count()
        self.message_user(request, f"Queued {updated} for /admin/ops (Commit Delete)")

# Add an ops link on the admin index page via site each_context (appears in template blocks)
def each_context(request):
    ctx = admin.site.each_context(request)
    ctx['gmb_ops_link'] = ops_link()
    return ctx
admin.site.each_context = each_context
