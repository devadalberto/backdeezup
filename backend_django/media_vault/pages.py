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
