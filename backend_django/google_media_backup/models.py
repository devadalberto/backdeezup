from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ── Validators ────────────────────────────────────────────────────────────────

def _validate_dict(value: object) -> None:
    if not isinstance(value, dict):
        raise ValidationError("Value must be a JSON object.")


def _validate_list(value: object) -> None:
    if not isinstance(value, list):
        raise ValidationError("Value must be a JSON array.")


# ── Media Item ────────────────────────────────────────────────────────────────

class MediaItem(models.Model):
    """
    De-duplicated local media blob, keyed by SHA-256.
    One row per unique file content regardless of how many Drive assets map to it.
    """

    sha256     = models.CharField(max_length=64, unique=True)
    file       = models.FileField(upload_to="imported/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"MediaItem {self.sha256[:12]}…"

    class Meta:
        verbose_name        = "Media Item"
        verbose_name_plural = "Media Items"
        ordering            = ["-created_at"]


# ── Drive Asset ───────────────────────────────────────────────────────────────

class DriveAsset(models.Model):

    class State(models.TextChoices):
        DISCOVERED    = "DISCOVERED",    "Discovered"
        DOWNLOADED    = "DOWNLOADED",    "Downloaded"
        IMPORTED      = "IMPORTED",      "Imported to Vault"
        VERIFIED      = "VERIFIED",      "Verified"
        DELETE_PENDING = "DELETE_PENDING", "Pending Deletion"
        DELETED       = "DELETED",       "Permanently Deleted"

    # Keep old-style constants as aliases so existing code doesn't break
    STATE_DISCOVERED    = State.DISCOVERED
    STATE_DOWNLOADED    = State.DOWNLOADED
    STATE_IMPORTED      = State.IMPORTED
    STATE_VERIFIED      = State.VERIFIED
    STATE_DELETE_PENDING = State.DELETE_PENDING
    STATE_DELETED       = State.DELETED
    STATE_CHOICES       = State.choices

    # Identity
    drive_id     = models.CharField(max_length=256, unique=True)
    name         = models.CharField(max_length=512)
    mime_type    = models.CharField(max_length=128)
    size_bytes   = models.BigIntegerField(default=0)
    md5_checksum = models.CharField(max_length=64, blank=True, default="")

    # FK — must come after identity fields per Django convention
    media_item = models.ForeignKey(
        "MediaItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drive_assets",
    )

    # State machine
    state = models.CharField(
        max_length=16, choices=State, default=State.DISCOVERED, db_index=True,
    )
    error = models.TextField(blank=True, default="")

    # Audit timeline
    discovered_at   = models.DateTimeField(default=timezone.now)
    downloaded_at   = models.DateTimeField(blank=True, null=True)
    download_path   = models.TextField(blank=True, default="")
    imported_at     = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.state}]"

    class Meta:
        verbose_name        = "Drive Asset"
        verbose_name_plural = "Drive Assets"
        indexes = [
            models.Index(fields=["state", "discovered_at"], name="drive_state_discovered_idx"),
            models.Index(fields=["state", "downloaded_at"], name="drive_state_downloaded_idx"),
            models.Index(fields=["state", "imported_at"],   name="drive_state_imported_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=[
                    "DISCOVERED", "DOWNLOADED", "IMPORTED",
                    "VERIFIED", "DELETE_PENDING", "DELETED",
                ]),
                name="driveasset_valid_state",
            ),
        ]


# ── Run Log ───────────────────────────────────────────────────────────────────

class RunLog(models.Model):
    """
    One row per pipeline run.

    totals schema:   {"discovered": int, "downloaded": int, "imported": int, "verified": int}
    error_log schema: [{"step": str, "error": str, "ts": ISO8601}, ...]
    """

    run_id      = models.CharField(max_length=64, unique=True)
    started_at  = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    status      = models.CharField(max_length=32, default="RUNNING")
    totals      = models.JSONField(default=dict, validators=[_validate_dict])
    error_log   = models.JSONField(default=list, validators=[_validate_list])

    def __str__(self) -> str:
        return f"Run {self.run_id} — {self.status}"

    class Meta:
        verbose_name        = "Run Log"
        verbose_name_plural = "Run Logs"
        ordering            = ["-started_at"]
        indexes             = [models.Index(fields=["-started_at"])]
