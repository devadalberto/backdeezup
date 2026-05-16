from django.db import models
from django.utils import timezone

class MediaItem(models.Model):
    sha256 = models.CharField(max_length=64, unique=True)
    file = models.FileField(upload_to='imported/')
    created_at = models.DateTimeField(auto_now_add=True)

class DriveAsset(models.Model):
    # State constants — use these instead of raw strings throughout the codebase
    STATE_DISCOVERED    = 'DISCOVERED'
    STATE_DOWNLOADED    = 'DOWNLOADED'
    STATE_IMPORTED      = 'IMPORTED'
    STATE_VERIFIED      = 'VERIFIED'
    STATE_DELETE_PENDING = 'DELETE_PENDING'
    STATE_DELETED       = 'DELETED'

    STATE_CHOICES = [
        (STATE_DISCOVERED,    'DISCOVERED'),
        (STATE_DOWNLOADED,    'DOWNLOADED'),
        (STATE_IMPORTED,      'IMPORTED'),
        (STATE_VERIFIED,      'VERIFIED'),
        (STATE_DELETE_PENDING,'DELETE_PENDING'),
        (STATE_DELETED,       'DELETED'),
    ]
    drive_id = models.CharField(max_length=256, unique=True)
    name = models.CharField(max_length=512)
    mime_type = models.CharField(max_length=128)
    size_bytes = models.BigIntegerField(default=0)
    md5_checksum = models.CharField(max_length=64, blank=True, null=True)
    discovered_at = models.DateTimeField(default=timezone.now)
    download_path = models.TextField(blank=True, null=True)
    downloaded_at = models.DateTimeField(blank=True, null=True)
    media_item = models.ForeignKey('MediaItem', on_delete=models.SET_NULL, null=True, blank=True)
    imported_at = models.DateTimeField(blank=True, null=True)
    state = models.CharField(max_length=16, choices=STATE_CHOICES, default=STATE_DISCOVERED, db_index=True)
    error = models.TextField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['state', 'discovered_at'], name='drive_state_discovered_idx'),
        ]

class RunLog(models.Model):
    run_id = models.CharField(max_length=64, unique=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=32, default='RUNNING')
    totals = models.JSONField(default=dict)
    error_log = models.JSONField(default=list)
