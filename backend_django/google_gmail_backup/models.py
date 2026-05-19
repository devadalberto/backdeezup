from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# ── Validators ────────────────────────────────────────────────────────────────

def _validate_list_of_strings(value: object) -> None:
    if not isinstance(value, list):
        raise ValidationError("Value must be a JSON array.")
    if not all(isinstance(v, str) for v in value):
        raise ValidationError("All array elements must be strings.")


# ── Gmail Sync State ──────────────────────────────────────────────────────────

class GmailSyncState(models.Model):
    """One row per synced Gmail account — tracks historyId for incremental sync."""

    email               = models.EmailField(unique=True)
    last_history_id     = models.CharField(max_length=64, blank=True, default="")
    last_full_sync_at   = models.DateTimeField(blank=True, null=True)
    last_incremental_at = models.DateTimeField(blank=True, null=True)
    total_messages      = models.IntegerField(default=0)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.email

    class Meta:
        verbose_name        = "Gmail Sync State"
        verbose_name_plural = "Gmail Sync States"
        ordering            = ["email"]


# ── Gmail Message ─────────────────────────────────────────────────────────────

class GmailMessage(models.Model):

    class State(models.TextChoices):
        DISCOVERED = "DISCOVERED", "Discovered"
        DOWNLOADED = "DOWNLOADED", "Downloaded"
        VERIFIED   = "VERIFIED",   "Verified"
        TRASHED    = "TRASHED",    "Trashed in Gmail"
        DELETED    = "DELETED",    "Permanently Deleted"

    # Keep old-style constants as aliases so existing code doesn't break
    STATE_DISCOVERED = State.DISCOVERED
    STATE_DOWNLOADED = State.DOWNLOADED
    STATE_VERIFIED   = State.VERIFIED
    STATE_TRASHED    = State.TRASHED
    STATE_DELETED    = State.DELETED
    STATE_CHOICES    = State.choices

    # Identity
    gmail_id   = models.CharField(max_length=64, unique=True)
    thread_id  = models.CharField(max_length=64, blank=True, default="", db_index=True)
    history_id = models.CharField(max_length=64, blank=True, default="")

    # Headers
    subject      = models.TextField(blank=True, default="")
    # RFC 5321 max address length is 320 chars; +display name overhead → 1000 is intentional
    from_address = models.CharField(max_length=1000, blank=True, default="")
    # to_address may contain multiple recipients separated by ", "
    to_address   = models.TextField(blank=True, default="")
    date         = models.DateTimeField(blank=True, null=True, db_index=True)
    snippet      = models.TextField(blank=True, default="")
    labels       = models.JSONField(default=list, validators=[_validate_list_of_strings])
    size_estimate     = models.IntegerField(default=0)
    has_attachments   = models.BooleanField(default=False)

    # Local backup
    raw_path = models.TextField(blank=True, default="")
    sha256   = models.CharField(max_length=64, blank=True, default="")

    # State machine
    state = models.CharField(
        max_length=20, choices=State, default=State.DISCOVERED, db_index=True,
    )
    error = models.TextField(blank=True, default="")

    # Audit timeline
    discovered_at   = models.DateTimeField(default=timezone.now)
    downloaded_at   = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)

    # account_email mirrors GmailSyncState.email — not a FK to prevent cascade on sync reset
    account_email = models.EmailField(
        db_index=True,
        help_text="Mirrors GmailSyncState.email — logical FK, not enforced at DB level.",
    )

    def __str__(self) -> str:
        return f"{self.subject or '(no subject)'} <{self.from_address}>"

    class Meta:
        verbose_name        = "Gmail Message"
        verbose_name_plural = "Gmail Messages"
        indexes = [
            models.Index(fields=["account_email", "state"]),
            models.Index(fields=["account_email", "date"]),
            models.Index(fields=["from_address"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(gmail_id=""),
                name="gmail_message_id_not_empty",
            ),
        ]


# ── Gmail Attachment ──────────────────────────────────────────────────────────

class GmailAttachment(models.Model):
    """An extracted attachment from a downloaded .eml file."""

    message       = models.ForeignKey(GmailMessage, on_delete=models.CASCADE, related_name="attachments")
    attachment_id = models.CharField(max_length=256)
    filename      = models.CharField(max_length=512, blank=True, default="")
    mime_type     = models.CharField(max_length=128, blank=True, default="")
    size          = models.IntegerField(default=0)
    sha256        = models.CharField(max_length=64, blank=True, default="")
    local_path    = models.TextField(blank=True, default="")
    downloaded_at = models.DateTimeField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.filename or self.attachment_id} ({self.mime_type})"

    class Meta:
        unique_together     = [("message", "attachment_id")]
        verbose_name        = "Gmail Attachment"
        verbose_name_plural = "Gmail Attachments"


# ── Protected Senders ─────────────────────────────────────────────────────────

class ProtectedSender(models.Model):
    """Emails from these senders are never trashed or deleted by any cleanup rule."""

    email          = models.EmailField(unique=True)
    label_to_apply = models.CharField(max_length=100, blank=True, default="")
    star           = models.BooleanField(default=False)
    note           = models.CharField(max_length=200, blank=True, default="")
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.email

    class Meta:
        verbose_name        = "Protected Sender"
        verbose_name_plural = "Protected Senders"
        ordering            = ["email"]


# ── Cleanup Rule ──────────────────────────────────────────────────────────────

class CleanupRule(models.Model):

    class Action(models.TextChoices):
        TRASH   = "trash",   "Move to Trash"
        STAR    = "star",    "Star"
        LABEL   = "label",   "Apply Label"
        ARCHIVE = "archive", "Archive (remove INBOX)"

    # Keep old-style constants as aliases
    ACTION_TRASH   = Action.TRASH
    ACTION_STAR    = Action.STAR
    ACTION_LABEL   = Action.LABEL
    ACTION_ARCHIVE = Action.ARCHIVE
    ACTION_CHOICES = Action.choices

    name        = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    gmail_query = models.TextField(
        help_text="Gmail search query, e.g. 'category:promotions older_than:30d'",
    )
    min_age_days = models.IntegerField(
        default=30,
        help_text="Minimum message age in days before rule applies (0 = any age)",
    )

    action     = models.CharField(max_length=20, choices=Action)
    label_name = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Label to apply (required when action=label)",
    )

    enabled                   = models.BooleanField(default=False)
    dry_run_default           = models.BooleanField(default=True)
    respect_protected_senders = models.BooleanField(default=True)

    last_run_at         = models.DateTimeField(blank=True, null=True)
    last_run_dry        = models.BooleanField(default=True)
    last_affected_count = models.IntegerField(default=0)
    last_dry_run_count  = models.IntegerField(default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="rules_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.name} [{status}]"

    class Meta:
        verbose_name        = "Cleanup Rule"
        verbose_name_plural = "Cleanup Rules"
        ordering            = ["name"]
        indexes             = [models.Index(fields=["enabled", "name"])]


# ── Rule Condition ────────────────────────────────────────────────────────────

class RuleCondition(models.Model):
    """
    A single condition inside a compound CleanupRule query.
    Conditions are ordered and joined by their `logic` field to build the Gmail q= string.

    Example (LinkedIn job emails):
      field=sender,  operator=contains,  value=linkedin.com,  logic=AND, order=1
      field=subject, operator=contains,  value=job,           logic=OR,  order=2
    → from:linkedin.com (subject:job)
    """

    class Field(models.TextChoices):
        SENDER     = "sender",         "Sender (from)"
        TO         = "to",             "Recipient (to)"
        SUBJECT    = "subject",        "Subject"
        BODY       = "body",           "Body"
        LABEL      = "label",          "Label"
        CATEGORY   = "category",       "Category"
        HAS_ATTACH = "has_attachment", "Has Attachment"
        AGE        = "age_days",       "Age (days)"

    class Operator(models.TextChoices):
        CONTAINS     = "contains",     "contains"
        NOT_CONTAINS = "not_contains", "does not contain"
        EQUALS       = "equals",       "equals"
        NOT_EQUALS   = "not_equals",   "does not equal"
        STARTS_WITH  = "starts_with",  "starts with"
        OLDER_THAN   = "older_than",   "older than"
        NEWER_THAN   = "newer_than",   "newer than"
        IS_TRUE      = "is_true",      "is true"

    class Logic(models.TextChoices):
        AND = "AND", "AND"
        OR  = "OR",  "OR"

    # Keep old-style constants as aliases
    FIELD_SENDER     = Field.SENDER
    FIELD_SUBJECT    = Field.SUBJECT
    FIELD_BODY       = Field.BODY
    FIELD_LABEL      = Field.LABEL
    FIELD_CATEGORY   = Field.CATEGORY
    FIELD_HAS_ATTACH = Field.HAS_ATTACH
    FIELD_AGE        = Field.AGE
    FIELD_TO         = Field.TO
    FIELD_CHOICES    = Field.choices

    OP_CONTAINS     = Operator.CONTAINS
    OP_NOT_CONTAINS = Operator.NOT_CONTAINS
    OP_EQUALS       = Operator.EQUALS
    OP_NOT_EQUALS   = Operator.NOT_EQUALS
    OP_STARTS_WITH  = Operator.STARTS_WITH
    OP_OLDER_THAN   = Operator.OLDER_THAN
    OP_NEWER_THAN   = Operator.NEWER_THAN
    OP_IS_TRUE      = Operator.IS_TRUE
    OP_CHOICES      = Operator.choices

    LOGIC_AND     = Logic.AND
    LOGIC_OR      = Logic.OR
    LOGIC_CHOICES = Logic.choices

    rule     = models.ForeignKey(CleanupRule, on_delete=models.CASCADE, related_name="conditions")
    order    = models.PositiveSmallIntegerField(default=0)
    field    = models.CharField(max_length=20, choices=Field)
    operator = models.CharField(max_length=20, choices=Operator)
    value    = models.CharField(max_length=500, blank=True, default="")
    logic    = models.CharField(
        max_length=3, choices=Logic, default=Logic.AND,
        help_text="How this condition joins with the NEXT condition",
    )

    def __str__(self) -> str:
        return f"{self.field} {self.operator} '{self.value}' ({self.logic})"

    class Meta:
        ordering            = ["order"]
        verbose_name        = "Rule Condition"
        verbose_name_plural = "Rule Conditions"


# ── Cleanup Audit Log ─────────────────────────────────────────────────────────

class CleanupAuditLog(models.Model):
    """Immutable append-only log of every cleanup action (dry-run or real)."""

    rule      = models.ForeignKey(
        CleanupRule, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    rule_name = models.CharField(max_length=200)
    action    = models.CharField(max_length=20, choices=CleanupRule.Action)
    dry_run   = models.BooleanField(default=True)

    actor       = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="audit_logs",
    )
    actor_label = models.CharField(max_length=100, default="system")

    affected_count        = models.IntegerField(default=0)
    affected_gmail_ids    = models.JSONField(
        default=list,
        validators=[_validate_list_of_strings],
        help_text="First 100 affected Gmail message IDs",
    )
    affected_ids_truncated = models.BooleanField(
        default=False,
        help_text="True when more than 100 messages were affected",
    )
    sample_subjects = models.JSONField(
        default=list,
        validators=[_validate_list_of_strings],
    )

    started_at  = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(blank=True, null=True)
    status      = models.CharField(max_length=20, default="OK")
    error_text  = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        prefix = "[DRY]" if self.dry_run else "[LIVE]"
        return f"{prefix} {self.rule_name} → {self.affected_count} affected"

    class Meta:
        verbose_name        = "Cleanup Audit Log"
        verbose_name_plural = "Cleanup Audit Logs"
        ordering            = ["-started_at"]
        indexes             = [
            models.Index(fields=["-started_at"]),
            models.Index(fields=["rule", "-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]
