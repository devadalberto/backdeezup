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
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup, IndexView as SnippetIndexView
from wagtail.images.views.images import IndexView as ImagesIndexView

from .models import MediaDecision, VaultDocument, VaultImage, VaultMedia

LIMIT_CHOICES = [20, 50, 100, 200]
DEFAULT_LIMIT = 30  # Wagtail default

# Patch Wagtail's images IndexView to honour ?limit= from the request
_orig_images_paginate_by = ImagesIndexView.get_paginate_by

def _patched_images_paginate_by(self, queryset):
    try:
        val = int(self.request.GET.get("limit", 0))
        if val in LIMIT_CHOICES:
            return val
    except (TypeError, ValueError):
        pass
    return _orig_images_paginate_by(self, queryset)

ImagesIndexView.get_paginate_by = _patched_images_paginate_by


# ── Matrix theme + listing controls injection ─────────────────────────────────

@hooks.register("insert_global_admin_css")
def matrix_admin_css():
    return format_html(
        '<link rel="stylesheet" href="{}">',
        static("media_vault/css/matrix_wagtail.css"),
    )


@hooks.register("insert_global_admin_js")
def listing_controls_js():
    return format_html(
        '<script src="{}"></script>',
        static("media_vault/js/listing_controls.js"),
    )


# ── Per-page limit IndexView ──────────────────────────────────────────────────

class LimitableIndexView(SnippetIndexView):
    def get_paginate_by(self, queryset):
        try:
            val = int(self.request.GET.get("limit", 0))
            if val in LIMIT_CHOICES:
                return val
        except (TypeError, ValueError):
            pass
        return DEFAULT_LIMIT


# ── SnippetViewSets for review workflow ───────────────────────────────────────

class VaultImageViewSet(SnippetViewSet):
    model = VaultImage
    icon = "image"
    menu_label = "Images"
    list_display = ["title", "source_type", "keep", "imported_at"]
    list_filter = ["keep", "source_type"]
    search_fields = ["title", "source_id"]
    ordering = ["-imported_at"]
    index_view_class = LimitableIndexView


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


class MediaVaultGroup(SnippetViewSetGroup):
    menu_label = "Media Vault"
    menu_icon = "folder-open-inverse"
    menu_order = 200
    items = [VaultImageViewSet, VaultMediaViewSet, VaultDocumentViewSet, MediaDecisionViewSet]


register_snippet(MediaVaultGroup)
