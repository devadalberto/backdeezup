from django.contrib.auth.models import User
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


class GmailMessage(models.Model):
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

    gmail_id = models.CharField(max_length=64, unique=True)
    thread_id = models.CharField(max_length=64, db_index=True)
    history_id = models.CharField(max_length=64, blank=True, null=True)

    subject = models.TextField(blank=True, default="")
    from_address = models.CharField(max_length=1000, blank=True, default="")
    to_address = models.TextField(blank=True, default="")
    date = models.DateTimeField(blank=True, null=True, db_index=True)
    snippet = models.TextField(blank=True, default="")
    labels = models.JSONField(default=list)
    size_estimate = models.IntegerField(default=0)
    has_attachments = models.BooleanField(default=False)

    raw_path = models.TextField(blank=True, null=True)
    sha256 = models.CharField(max_length=64, blank=True, null=True)

    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_DISCOVERED, db_index=True)
    error = models.TextField(blank=True, null=True)

    discovered_at = models.DateTimeField(default=timezone.now)
    downloaded_at = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    account_email = models.EmailField(db_index=True)

    def __str__(self):
        return f"{self.subject or '(no subject)'} <{self.from_address}>"

    class Meta:
        verbose_name = "Gmail Message"
        indexes = [
            models.Index(fields=["account_email", "state"]),
            models.Index(fields=["account_email", "date"]),
            models.Index(fields=["from_address"]),
        ]


class GmailAttachment(models.Model):
    message = models.ForeignKey(GmailMessage, on_delete=models.CASCADE, related_name="attachments")
    attachment_id = models.CharField(max_length=256)
    filename = models.CharField(max_length=512, blank=True, default="")
    mime_type = models.CharField(max_length=128, blank=True, default="")
    size = models.IntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, null=True)
    local_path = models.TextField(blank=True, null=True)
    downloaded_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = [("message", "attachment_id")]


# ── Cleanup rules engine ──────────────────────────────────────────────────────

class ProtectedSender(models.Model):
    """Emails from these senders are always kept — never trashed, never deleted."""
    email = models.EmailField(unique=True)
    label_to_apply = models.CharField(max_length=100, blank=True, default="")
    star = models.BooleanField(default=False)
    note = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

    class Meta:
        verbose_name = "Protected Sender"
        ordering = ["email"]


class CleanupRule(models.Model):
    ACTION_TRASH = "trash"
    ACTION_STAR = "star"
    ACTION_LABEL = "label"
    ACTION_ARCHIVE = "archive"

    ACTION_CHOICES = [
        (ACTION_TRASH, "Move to Trash"),
        (ACTION_STAR, "Star"),
        (ACTION_LABEL, "Apply Label"),
        (ACTION_ARCHIVE, "Archive (remove INBOX)"),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    # Gmail query syntax — same as the Gmail search box
    gmail_query = models.TextField(help_text="Gmail search query, e.g. 'category:promotions older_than:30d'")

    # Local DB filter applied in addition to gmail_query results (optional)
    min_age_days = models.IntegerField(default=30, help_text="Minimum age in days before rule applies")

    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    label_name = models.CharField(max_length=100, blank=True, default="",
                                  help_text="Label to apply (for action=label)")

    enabled = models.BooleanField(default=False)
    dry_run_default = models.BooleanField(default=True)
    respect_protected_senders = models.BooleanField(default=True)

    # Stats from last run
    last_run_at = models.DateTimeField(blank=True, null=True)
    last_run_dry = models.BooleanField(default=True)
    last_affected_count = models.IntegerField(default=0)
    last_dry_run_count = models.IntegerField(default=0)

    created_by = models.ForeignKey(User, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="rules_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'enabled' if self.enabled else 'disabled'})"

    class Meta:
        verbose_name = "Cleanup Rule"
        ordering = ["name"]


class RuleCondition(models.Model):
    """
    A single condition in a compound rule query.
    Multiple conditions are AND/OR-combined to produce a Gmail q= string.

    Example (LinkedIn jobs):
      field=sender,  operator=contains,     value=linkedin.com,  logic=AND, order=1
      field=subject, operator=contains,     value=job,           logic=OR,  order=2
      field=subject, operator=contains,     value=recruiter,     logic=OR,  order=3
      field=subject, operator=contains,     value=applied,       logic=OR,  order=4
    → from:linkedin.com (subject:job OR subject:recruiter OR subject:applied)
    """
    FIELD_SENDER     = "sender"
    FIELD_SUBJECT    = "subject"
    FIELD_BODY       = "body"
    FIELD_LABEL      = "label"
    FIELD_CATEGORY   = "category"
    FIELD_HAS_ATTACH = "has_attachment"
    FIELD_AGE        = "age_days"
    FIELD_TO         = "to"

    FIELD_CHOICES = [
        (FIELD_SENDER,     "Sender (from)"),
        (FIELD_TO,         "Recipient (to)"),
        (FIELD_SUBJECT,    "Subject"),
        (FIELD_BODY,       "Body"),
        (FIELD_LABEL,      "Label"),
        (FIELD_CATEGORY,   "Category"),
        (FIELD_HAS_ATTACH, "Has Attachment"),
        (FIELD_AGE,        "Age (days)"),
    ]

    OP_CONTAINS     = "contains"
    OP_NOT_CONTAINS = "not_contains"
    OP_EQUALS       = "equals"
    OP_NOT_EQUALS   = "not_equals"
    OP_STARTS_WITH  = "starts_with"
    OP_OLDER_THAN   = "older_than"
    OP_NEWER_THAN   = "newer_than"
    OP_IS_TRUE      = "is_true"

    OP_CHOICES = [
        (OP_CONTAINS,     "contains"),
        (OP_NOT_CONTAINS, "does not contain"),
        (OP_EQUALS,       "equals"),
        (OP_NOT_EQUALS,   "does not equal"),
        (OP_STARTS_WITH,  "starts with"),
        (OP_OLDER_THAN,   "older than"),
        (OP_NEWER_THAN,   "newer than"),
        (OP_IS_TRUE,      "is true"),
    ]

    LOGIC_AND = "AND"
    LOGIC_OR  = "OR"
    LOGIC_CHOICES = [(LOGIC_AND, "AND"), (LOGIC_OR, "OR")]

    rule     = models.ForeignKey(CleanupRule, on_delete=models.CASCADE, related_name="conditions")
    order    = models.PositiveSmallIntegerField(default=0)
    field    = models.CharField(max_length=20, choices=FIELD_CHOICES)
    operator = models.CharField(max_length=20, choices=OP_CHOICES)
    value    = models.CharField(max_length=500, blank=True, default="")
    logic    = models.CharField(max_length=3, choices=LOGIC_CHOICES, default=LOGIC_AND,
                                help_text="How this condition joins with the NEXT condition")

    class Meta:
        ordering = ["order"]
        verbose_name = "Rule Condition"

    def __str__(self):
        return f"{self.field} {self.operator} '{self.value}' ({self.logic})"


class CleanupAuditLog(models.Model):
    """Immutable log of every cleanup action (dry-run or real)."""
    rule = models.ForeignKey(CleanupRule, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="audit_logs")
    rule_name = models.CharField(max_length=200)
    action = models.CharField(max_length=20)
    dry_run = models.BooleanField(default=True)
    actor = models.ForeignKey(User, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="audit_logs")
    actor_label = models.CharField(max_length=100, default="system")

    affected_count = models.IntegerField(default=0)
    affected_gmail_ids = models.JSONField(default=list, help_text="First 100 IDs max")
    affected_ids_truncated = models.BooleanField(default=False, help_text="True when >100 IDs were affected")
    sample_subjects = models.JSONField(default=list)

    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, default="OK")
    error_text = models.TextField(blank=True, default="")

    class Meta:
        verbose_name = "Cleanup Audit Log"
        ordering = ["-started_at"]
        # Append-only: no update permission in admin
