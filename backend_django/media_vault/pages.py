"""
Wagtail page models for the Media Vault.
Templates use the Matrix theme and match the existing admin aesthetic.
"""
from django.db import models
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail import blocks
from wagtail.images.blocks import ImageBlock
from wagtailmedia.blocks import VideoChooserBlock, AudioChooserBlock


# ── Reusable blocks ───────────────────────────────────────────────────────────

class KeepDecisionBlock(blocks.ChoiceBlock):
    choices = [
        ("keep",      "Keep"),
        ("delete",    "Delete"),
        ("undecided", "Undecided"),
    ]
    default = "undecided"

    class Meta:
        icon = "tick"
        label = "Decision"


class CaptionedImageBlock(blocks.StructBlock):
    image   = ImageBlock()
    caption = blocks.CharBlock(required=False, max_length=200)
    credit  = blocks.CharBlock(required=False, max_length=100, label="Photo credit")
    keep    = KeepDecisionBlock()

    class Meta:
        icon = "image"
        label = "Image"
        template = "media_vault/blocks/captioned_image.html"


class VideoBlock(blocks.StructBlock):
    video   = VideoChooserBlock()
    caption = blocks.CharBlock(required=False, max_length=200)
    autoplay = blocks.BooleanBlock(default=False, required=False)
    loop     = blocks.BooleanBlock(default=False, required=False)
    keep     = KeepDecisionBlock()

    class Meta:
        icon = "media"
        label = "Video"
        template = "media_vault/blocks/video_block.html"


class AudioBlock(blocks.StructBlock):
    audio   = AudioChooserBlock()
    caption = blocks.CharBlock(required=False, max_length=200)
    keep    = KeepDecisionBlock()

    class Meta:
        icon = "media"
        label = "Audio"
        template = "media_vault/blocks/audio_block.html"


class GalleryBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=200)
    items   = blocks.ListBlock(CaptionedImageBlock(), min_num=1)

    class Meta:
        icon = "image"
        label = "Image Gallery"
        template = "media_vault/blocks/gallery_block.html"


class VideoGalleryBlock(blocks.StructBlock):
    heading = blocks.CharBlock(required=False, max_length=200)
    items   = blocks.ListBlock(VideoBlock(), min_num=1)

    class Meta:
        icon = "media"
        label = "Video Gallery"
        template = "media_vault/blocks/video_gallery_block.html"


VAULT_STREAM_BLOCKS = [
    ("image",         CaptionedImageBlock()),
    ("gallery",       GalleryBlock()),
    ("video",         VideoBlock()),
    ("video_gallery", VideoGalleryBlock()),
    ("audio",         AudioBlock()),
    ("text",          blocks.RichTextBlock(features=["bold", "italic", "link", "ul", "ol"])),
    ("heading",       blocks.CharBlock(classname="title", max_length=200)),
    ("raw_html",      blocks.RawHTMLBlock(label="Raw HTML")),
]


# ── Page models ───────────────────────────────────────────────────────────────

class MediaGalleryPage(Page):
    """
    General media gallery — mix of images, videos, and text.
    Most common page type for browsing backed-up media.
    """
    intro = models.TextField(blank=True, default="")
    body = StreamField(VAULT_STREAM_BLOCKS, use_json_field=True, blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Media Gallery Page"

    def get_context(self, request, *args, **kwargs):
        ctx = super().get_context(request, *args, **kwargs)
        ctx["filter_keep"] = request.GET.get("keep", "")
        return ctx


class PhotoReviewPage(Page):
    """
    Photo-only review page — scroll through images and mark keep/delete.
    Optimised for bulk triage of Drive/Photos media.
    """
    source_filter = models.CharField(
        max_length=20,
        choices=[("all", "All sources"), ("drive", "Drive only"), ("gmail", "Gmail only")],
        default="all",
    )
    body = StreamField(
        [("gallery", GalleryBlock()), ("image", CaptionedImageBlock())],
        use_json_field=True, blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("source_filter"),
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Photo Review Page"


class VideoReviewPage(Page):
    """
    Video-only review page — watch and mark keep/delete.
    """
    body = StreamField(
        [("video_gallery", VideoGalleryBlock()), ("video", VideoBlock())],
        use_json_field=True, blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Video Review Page"


class VaultHomePage(Page):
    """
    Landing page for the media vault — links to sub-pages, shows summary stats.
    """
    intro   = models.TextField(blank=True, default="")
    tagline = models.CharField(max_length=200, blank=True, default="Your Google media, organized.")

    content_panels = Page.content_panels + [
        MultiFieldPanel([FieldPanel("tagline"), FieldPanel("intro")], heading="Header"),
    ]

    class Meta:
        verbose_name = "Vault Home Page"


class GalleryIndexPage(Page):
    """
    Stash-style gallery index — live-queries VaultImage + VaultMedia with
    sidebar filters: person tag, media type, date range.
    No StreamField — content is dynamic from the DB.
    """
    intro = models.TextField(blank=True, default="")
    items_per_page = models.IntegerField(default=48)

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("items_per_page"),
    ]

    class Meta:
        verbose_name = "Gallery Index Page"

    def get_context(self, request, *args, **kwargs):
        from media_vault.models import VaultImage, VaultMedia, IDENTITY_TAG_CHOICES
        from taggit.models import Tag
        from django.core.paginator import Paginator
        from django.db.models import Q

        ctx = super().get_context(request, *args, **kwargs)

        # ── Filters from GET params ───────────────────────────────────────
        person   = request.GET.get("person", "")
        mtype    = request.GET.get("type", "")     # image | video | all
        tag_slug = request.GET.get("tag", "")
        q_search = request.GET.get("q", "")
        page_num = int(request.GET.get("page", 1))

        # ── Build querysets ───────────────────────────────────────────────
        images_qs = VaultImage.objects.order_by("-imported_at")
        videos_qs = VaultMedia.objects.order_by("-imported_at")

        if person:
            images_qs = images_qs.filter(identity_tag=person)
            videos_qs = videos_qs.filter(identity_tag=person)

        if tag_slug:
            images_qs = images_qs.filter(tags__slug=tag_slug)
            videos_qs = videos_qs.filter(tags__slug=tag_slug)

        if q_search:
            images_qs = images_qs.filter(
                Q(title__icontains=q_search) | Q(source_email__icontains=q_search)
            )
            videos_qs = videos_qs.filter(
                Q(title__icontains=q_search) | Q(source_email__icontains=q_search)
            )

        # ── Combine into unified list for grid ────────────────────────────
        if mtype == "image":
            items = [("image", img) for img in images_qs]
            total = images_qs.count()
        elif mtype == "video":
            items = [("video", vid) for vid in videos_qs]
            total = videos_qs.count()
        else:
            # Interleave: sort images + videos together by imported_at
            combined = (
                [("image", img) for img in images_qs] +
                [("video", vid) for vid in videos_qs]
            )
            combined.sort(key=lambda x: x[1].imported_at, reverse=True)
            items = combined
            total = len(items)

        # ── Paginate ──────────────────────────────────────────────────────
        paginator = Paginator(items, self.items_per_page)
        page_obj = paginator.get_page(page_num)

        # ── Sidebar data ──────────────────────────────────────────────────
        all_tags = Tag.objects.filter(
            Q(media_vault_vaultimage_tags__isnull=False) |
            Q(media_vault_vaultmedia_tags__isnull=False)
        ).distinct().order_by("name")

        ctx.update({
            "page_obj": page_obj,
            "items": page_obj.object_list,
            "total": total,
            "identity_choices": IDENTITY_TAG_CHOICES,
            "all_tags": all_tags,
            # active filters
            "active_person": person,
            "active_type": mtype,
            "active_tag": tag_slug,
            "active_q": q_search,
            # counts for sidebar badges
            "count_images": VaultImage.objects.count(),
            "count_videos": VaultMedia.objects.count(),
        })
        return ctx
