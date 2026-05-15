from django.db import models
from django.utils import timezone


class GmailSyncState(models.Model):
    """One row per synced account — tracks historyId for incremental sync."""
    email = models.EmailField(unique=True)
    last_history_id = models.CharField(max_length=64, blank=True, null=True)
    last_full_sync_at = models.DateTimeField(blank=True, null=True)
    last_incremental_at = models.DateTimeField(blank=True, null=True)
    total_messages = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = "Gmail Sync State"
        verbose_name_plural = "Gmail Sync States"


class GmailMessage(models.Model):
    """One row per Gmail message discovered and/or downloaded."""

    STATE_DISCOVERED = "DISCOVERED"
    STATE_DOWNLOADED = "DOWNLOADED"
    STATE_VERIFIED = "VERIFIED"
    STATE_TRASHED = "TRASHED"
    STATE_DELETED = "DELETED"

    STATE_CHOICES = [
        (STATE_DISCOVERED, "Discovered"),
        (STATE_DOWNLOADED, "Downloaded"),
        (STATE_VERIFIED, "Verified"),
        (STATE_TRASHED, "Trashed in Gmail"),
        (STATE_DELETED, "Permanently Deleted"),
    ]

    # Gmail identifiers
    gmail_id = models.CharField(max_length=64, unique=True)
    thread_id = models.CharField(max_length=64, db_index=True)
    history_id = models.CharField(max_length=64, blank=True, null=True)

    # Metadata (populated on DISCOVERED)
    subject = models.TextField(blank=True, default="")
    from_address = models.CharField(max_length=1000, blank=True, default="")
    to_address = models.TextField(blank=True, default="")
    date = models.DateTimeField(blank=True, null=True, db_index=True)
    snippet = models.TextField(blank=True, default="")
    labels = models.JSONField(default=list)
    size_estimate = models.IntegerField(default=0)
    has_attachments = models.BooleanField(default=False)

    # Local storage (populated on DOWNLOADED)
    raw_path = models.TextField(blank=True, null=True)
    sha256 = models.CharField(max_length=64, blank=True, null=True)

    # Pipeline state
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_DISCOVERED, db_index=True)
    error = models.TextField(blank=True, null=True)

    # Timestamps
    discovered_at = models.DateTimeField(default=timezone.now)
    downloaded_at = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)

    # Account
    account_email = models.EmailField(db_index=True)

    def __str__(self):
        return f"{self.subject or '(no subject)'} <{self.from_address}>"

    class Meta:
        verbose_name = "Gmail Message"
        verbose_name_plural = "Gmail Messages"
        indexes = [
            models.Index(fields=["account_email", "state"]),
            models.Index(fields=["account_email", "date"]),
            models.Index(fields=["from_address"]),
        ]


class GmailAttachment(models.Model):
    """Attachment metadata for a GmailMessage."""
    message = models.ForeignKey(GmailMessage, on_delete=models.CASCADE, related_name="attachments")
    attachment_id = models.CharField(max_length=256)
    filename = models.CharField(max_length=512, blank=True, default="")
    mime_type = models.CharField(max_length=128, blank=True, default="")
    size = models.IntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, null=True)
    local_path = models.TextField(blank=True, null=True)
    downloaded_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.filename} ({self.mime_type})"

    class Meta:
        verbose_name = "Gmail Attachment"
        unique_together = [("message", "attachment_id")]
