from django.db import models
# Page models imported here so Django/Wagtail discover them
from .pages import MediaGalleryPage, PhotoReviewPage, VaultHomePage, VideoReviewPage  # noqa: F401
from django.utils import timezone
from wagtail.images.models import AbstractImage, AbstractRendition
from wagtail.documents.models import AbstractDocument
from wagtailmedia.models import AbstractMedia


class MediaMetadata(models.Model):
    """
    Preserved EXIF/metadata from a media file BEFORE it was stripped.
    Linked to the source file path (not VaultImage FK — metadata is extracted
    during attachment phase, before vault import).
    Immutable — append-only. Never update, never delete.
    """
    # Source identification
    source_path = models.TextField(unique=True, help_text="Absolute path to the stripped file")
    source_sha256 = models.CharField(max_length=64, blank=True, db_index=True)
    gmail_message_id = models.CharField(max_length=256, blank=True, db_index=True)
    filename = models.CharField(max_length=512, blank=True)
    mime_type = models.CharField(max_length=128, blank=True)

    # Preserved metadata (JSON — full EXIF dump)
    raw_exif = models.JSONField(default=dict, help_text="Full EXIF tag dump before strip")

    # Key fields extracted for quick querying
    device_make = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    datetime_original = models.DateTimeField(null=True, blank=True)
    datetime_digitized = models.DateTimeField(null=True, blank=True)
    software = models.CharField(max_length=200, blank=True)

    # GPS (stored as decimal degrees for easy querying)
    gps_latitude = models.FloatField(null=True, blank=True)
    gps_longitude = models.FloatField(null=True, blank=True)
    gps_altitude = models.FloatField(null=True, blank=True)
    gps_speed = models.FloatField(null=True, blank=True)
    gps_timestamp = models.DateTimeField(null=True, blank=True)

    # Strip audit
    stripped_at = models.DateTimeField(auto_now_add=True)
    original_size_bytes = models.IntegerField(default=0)
    stripped_size_bytes = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Media Metadata"
        verbose_name_plural = "Media Metadata Records"
        ordering = ["-stripped_at"]

    def __str__(self):
        return f"{self.filename} ({self.device_make} {self.device_model})"


class VaultImage(AbstractImage):
    """
    Custom Wagtail image model.
    Links back to source (Drive asset or Gmail attachment).
    """
    source_type = models.CharField(
        max_length=20,
        choices=[("drive", "Google Drive"), ("gmail", "Gmail Attachment"), ("upload", "Manual Upload")],
        default="upload",
    )
    source_id = models.CharField(max_length=256, blank=True, default="")
    source_email = models.EmailField(blank=True, default="")
    imported_at = models.DateTimeField(default=timezone.now)
    keep = models.BooleanField(default=None, null=True, help_text="None=undecided, True=keep, False=delete")
    notes = models.TextField(blank=True, default="")

    admin_form_fields = (
        "title", "file", "collection", "tags", "focal_point_x", "focal_point_y",
        "focal_point_width", "focal_point_height",
        "source_type", "keep", "notes",
    )

    class Meta(AbstractImage.Meta):
        verbose_name = "Vault Image"


class VaultRendition(AbstractRendition):
    image = models.ForeignKey(VaultImage, on_delete=models.CASCADE, related_name="renditions")

    class Meta:
        unique_together = (("image", "filter_spec", "focal_point_key"),)


class VaultDocument(AbstractDocument):
    """Custom document model for PDFs and other non-media files."""
    source_type = models.CharField(max_length=20, default="upload")
    source_id = models.CharField(max_length=256, blank=True, default="")
    keep = models.BooleanField(default=None, null=True)

    admin_form_fields = ("title", "file", "collection", "tags", "source_type", "keep")

    class Meta:
        verbose_name = "Vault Document"


class VaultMedia(AbstractMedia):
    """
    Custom wagtailmedia model for video and audio files.
    Links to source Drive asset or Gmail attachment.
    """
    source_type = models.CharField(
        max_length=20,
        choices=[("drive", "Google Drive"), ("gmail", "Gmail Attachment"), ("upload", "Manual Upload")],
        default="upload",
    )
    source_id = models.CharField(max_length=256, blank=True, default="")
    source_email = models.EmailField(blank=True, default="")
    imported_at = models.DateTimeField(default=timezone.now)
    keep = models.BooleanField(default=None, null=True, help_text="None=undecided, True=keep, False=delete")
    notes = models.TextField(blank=True, default="")
    duration_seconds = models.IntegerField(default=0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)

    admin_form_fields = (
        "title", "file", "collection", "thumbnail",
        "source_type", "duration_seconds", "keep", "notes",
    )

    class Meta(AbstractMedia.Meta):
        verbose_name = "Vault Media"


class MediaDecision(models.Model):
    """Tracks keep/delete decisions on vault items with audit trail."""
    ITEM_TYPE_IMAGE = "image"
    ITEM_TYPE_VIDEO = "video"
    ITEM_TYPE_DOCUMENT = "document"

    TYPE_CHOICES = [
        (ITEM_TYPE_IMAGE, "Image"),
        (ITEM_TYPE_VIDEO, "Video"),
        (ITEM_TYPE_DOCUMENT, "Document"),
    ]

    ACTION_KEEP = "keep"
    ACTION_DELETE = "delete"
    ACTION_UNDECIDED = "undecided"

    ACTION_CHOICES = [
        (ACTION_KEEP, "Keep"),
        (ACTION_DELETE, "Delete"),
        (ACTION_UNDECIDED, "Undecided"),
    ]

    item_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    item_id = models.IntegerField()
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_UNDECIDED)
    notes = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.CharField(max_length=100, default="user")

    class Meta:
        verbose_name = "Media Decision"
        ordering = ["-decided_at"]
        indexes = [models.Index(fields=["item_type", "item_id"])]
