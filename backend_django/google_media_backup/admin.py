# backend_django/google_media_backup/admin.py
from django.contrib import admin
from django.conf import settings
from .models import DriveAsset, MediaItem, RunLog

# Branding from .env via settings (optional)
admin.site.site_header = getattr(settings, "ADMIN_SITE_HEADER", "Gmail Media Cleanup Admin")
admin.site.site_title = getattr(settings, "ADMIN_SITE_TITLE", "Gmail Media Cleanup")
admin.site.index_title = getattr(settings, "ADMIN_INDEX_TITLE", "Operations Console")

# IMPORTANT: Do NOT override admin.site.each_context here.
# That was the source of the RecursionError.

@admin.register(MediaItem)
class MediaItemAdmin(admin.ModelAdmin):
    list_display = ("sha256", "file", "created_at")
    search_fields = ("sha256", "file")


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ("run_id", "status", "started_at", "finished_at")
    search_fields = ("run_id", "status")
    readonly_fields = ("started_at", "finished_at", "totals")


@admin.register(DriveAsset)
class DriveAssetAdmin(admin.ModelAdmin):
    list_display = ("drive_id", "name", "mime_type", "state", "download_path", "imported_at")
    list_filter = ("state", "mime_type")
    search_fields = ("drive_id", "name", "mime_type")
    readonly_fields = ("discovered_at", "downloaded_at", "imported_at", "last_attempt_at")

    actions = ["action_mark_delete", "action_commit_delete", "action_export_zip", "action_export_tar"]

    @admin.action(description="Mark selected as DELETE_PENDING (only if VERIFIED)")
    def action_mark_delete(self, request, queryset):
        updated = queryset.filter(state="VERIFIED").update(state="DELETE_PENDING")
        self.message_user(request, f"Marked {updated} item(s) as DELETE_PENDING.")

    @admin.action(description="Queue selected for Drive delete (commit via API)")
    def action_commit_delete(self, request, queryset):
        count = queryset.filter(state="DELETE_PENDING").count()
        self.message_user(
            request,
            f"{count} item(s) are in DELETE_PENDING. Use /admin/ops/ → Commit Delete to perform Drive delete."
        )

    def _export_selected(self, request, queryset, fmt):
        """Phase 36 — stream the selected assets as a ZIP/TAR + manifest.json."""
        from django.http import StreamingHttpResponse

        from core.export import archive_content_type, archive_filename, iter_archive_stream, resolve_export_items

        items = resolve_export_items("selection", media_ids=list(queryset.values_list("pk", flat=True)))
        if not items:
            self.message_user(request, "Nothing to export — none of the selected assets have a file on disk.", level="warning")
            return None
        resp = StreamingHttpResponse(iter_archive_stream(items, fmt), content_type=archive_content_type(fmt))
        resp["Content-Disposition"] = f'attachment; filename="{archive_filename("selection", fmt)}"'
        return resp

    @admin.action(description="Export selected as ZIP")
    def action_export_zip(self, request, queryset):
        return self._export_selected(request, queryset, "zip")

    @admin.action(description="Export selected as TAR")
    def action_export_tar(self, request, queryset):
        return self._export_selected(request, queryset, "tar")
