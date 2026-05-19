"""
Wagtail hooks for media_vault:
- Matrix CSS theme injection
- SnippetViewSet registrations for keep/delete review
- Custom menu items
"""
from django.templatetags.static import static
from django.utils.html import format_html
from wagtail import hooks
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import MediaDecision, MediaMetadata, VaultDocument, VaultImage, VaultMedia


# ── Matrix theme injection ────────────────────────────────────────────────────

@hooks.register("insert_global_admin_css")
def matrix_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("media_vault/css/matrix_wagtail.css"),
    )


# ── SnippetViewSets for review workflow ───────────────────────────────────────

class VaultImageViewSet(SnippetViewSet):
    model = VaultImage
    icon = "image"
    menu_label = "Images"
    list_display = ["title", "source_type", "keep", "imported_at"]
    list_filter = ["keep", "source_type"]
    search_fields = ["title", "source_id"]
    ordering = ["-imported_at"]


class VaultMediaViewSet(SnippetViewSet):
    model = VaultMedia
    icon = "media"
    menu_label = "Videos & Audio"
    list_display = ["title", "type", "keep", "imported_at"]
    list_filter = ["keep", "type", "source_type"]
    search_fields = ["title", "source_id"]
    ordering = ["-imported_at"]


class VaultDocumentViewSet(SnippetViewSet):
    model = VaultDocument
    icon = "doc-full"
    menu_label = "Documents"
    list_display = ["title", "source_type", "keep"]
    list_filter = ["keep", "source_type"]
    search_fields = ["title", "source_id"]


class MediaDecisionViewSet(SnippetViewSet):
    model = MediaDecision
    icon = "tick"
    menu_label = "Decisions Log"
    list_display = ["item_type", "item_id", "action", "decided_by", "decided_at"]
    list_filter = ["action", "item_type"]
    ordering = ["-decided_at"]

    def get_queryset(self, request):
        return super().get_queryset(request)

    # Audit log — read-only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class MediaMetadataViewSet(SnippetViewSet):
    model = MediaMetadata
    icon = "tag"
    menu_label = "EXIF Records"
    list_display = ["filename", "device_make", "device_model", "datetime_original", "gps_latitude", "gps_longitude", "stripped_at"]
    list_filter = ["device_make", "mime_type"]
    search_fields = ["filename", "device_make", "device_model", "gmail_message_id"]
    ordering = ["-stripped_at"]

    # Read-only — metadata is immutable audit trail
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


class MediaVaultGroup(SnippetViewSetGroup):
    menu_label = "Media Vault"
    menu_icon = "folder-open-inverse"
    menu_order = 200
    items = [VaultImageViewSet, VaultMediaViewSet, VaultDocumentViewSet, MediaDecisionViewSet, MediaMetadataViewSet]


register_snippet(MediaVaultGroup)
