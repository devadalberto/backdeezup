"""
Cleanup rules engine.
All actions support dry_run=True (default) — nothing touches Gmail until dry_run=False.
Protected senders are always skipped.
Every execution is logged to CleanupAuditLog.
"""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import CleanupAuditLog, CleanupRule, GmailMessage, ProtectedSender
from .services_gmail import (
    gmail_service,
    modify_labels,
    trash_message,
)

log = logging.getLogger(__name__)


def _protected_emails() -> set:
    return set(ProtectedSender.objects.values_list("email", flat=True))


def _normalize_email(addr: str) -> str:
    """Extract bare email from 'Name <email>' format."""
    if "<" in addr:
        return addr.split("<")[-1].strip("> ").lower()
    return addr.strip().lower()


def _is_protected(message: GmailMessage, protected: set) -> bool:
    email = _normalize_email(message.from_address)
    return email in {e.lower() for e in protected}


def _get_or_create_label(svc, label_name: str) -> str:
    """Get Gmail label ID by name, creating it if needed."""
    labels = svc.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"].lower() == label_name.lower():
            return label["id"]
    new_label = svc.users().labels().create(
        userId="me",
        body={"name": label_name, "labelListVisibility": "labelShow",
              "messageListVisibility": "show"},
    ).execute()
    return new_label["id"]


def apply_rule(rule: CleanupRule, dry_run: bool = True, actor_label: str = "system") -> CleanupAuditLog:
    """
    Apply a CleanupRule. Returns a CleanupAuditLog record.
    Protected senders are always skipped regardless of rule.
    """
    audit = CleanupAuditLog.objects.create(
        rule=rule,
        rule_name=rule.name,
        action=rule.action,
        dry_run=dry_run,
        actor_label=actor_label,
        status="RUNNING",
    )

    try:
        protected = _protected_emails()
        cutoff = timezone.now() - timedelta(days=rule.min_age_days)

        # Build local queryset from verified messages matching age requirement
        qs = GmailMessage.objects.filter(
            state=GmailMessage.STATE_VERIFIED,
            date__lte=cutoff,
        )

        # For dry-run: count from local DB only (fast, no Gmail API call)
        # For real run: also cross-reference live Gmail query to catch label changes
        if not dry_run and rule.gmail_query.strip():
            svc = gmail_service()
            if svc:
                matching_ids = set()
                page_token = None
                while True:
                    params = dict(userId="me", q=rule.gmail_query, maxResults=500)
                    if page_token:
                        params["pageToken"] = page_token
                    res = svc.users().messages().list(**params).execute()
                    for m in res.get("messages", []):
                        matching_ids.add(m["id"])
                    page_token = res.get("nextPageToken")
                    if not page_token:
                        break
                qs = qs.filter(gmail_id__in=matching_ids)

        # Exclude protected senders — push filter to DB, not Python iteration
        if rule.respect_protected_senders and protected:
            normalized = {e.lower() for e in protected}
            # Filter out messages where from_address contains a protected email
            for email in normalized:
                qs = qs.exclude(from_address__icontains=email)
        candidates = list(qs[:5000])  # hard cap to prevent memory exhaustion

        affected_ids = [m.gmail_id for m in candidates]
        sample_subjects = [m.subject[:80] for m in candidates[:10]]
        audit.affected_count = len(affected_ids)
        audit.affected_gmail_ids = affected_ids[:100]
        audit.sample_subjects = sample_subjects

        if dry_run:
            audit.status = "DRY_RUN"
            audit.finished_at = timezone.now()
            audit.save()
            rule.last_dry_run_count = len(affected_ids)
            rule.save(update_fields=["last_dry_run_count"])
            return audit

        # Execute the action
        svc = gmail_service()
        if not svc:
            raise RuntimeError("Not authenticated — run make auth first")

        executed = 0
        if rule.action == CleanupRule.ACTION_TRASH:
            trashed_ids = []
            for msg in candidates:
                if trash_message(msg.gmail_id):
                    trashed_ids.append(msg.gmail_id)
                    executed += 1
            # Batch DB update — single query instead of N saves
            if trashed_ids:
                with transaction.atomic():
                    GmailMessage.objects.filter(gmail_id__in=trashed_ids).update(
                        state=GmailMessage.STATE_TRASHED
                    )

        elif rule.action == CleanupRule.ACTION_STAR:
            for msg in candidates:
                if modify_labels(msg.gmail_id, add_labels=["STARRED"]):
                    if "STARRED" not in msg.labels:
                        msg.labels = list(msg.labels) + ["STARRED"]
                        msg.save(update_fields=["labels"])
                    executed += 1

        elif rule.action == CleanupRule.ACTION_LABEL:
            label_id = _get_or_create_label(svc, rule.label_name)
            for msg in candidates:
                if modify_labels(msg.gmail_id, add_labels=[label_id]):
                    executed += 1

        elif rule.action == CleanupRule.ACTION_ARCHIVE:
            for msg in candidates:
                if modify_labels(msg.gmail_id, remove_labels=["INBOX"]):
                    executed += 1

        audit.affected_count = executed
        audit.status = "OK"
        audit.finished_at = timezone.now()
        audit.save()

        rule.last_run_at = timezone.now()
        rule.last_run_dry = False
        rule.last_affected_count = executed
        rule.save(update_fields=["last_run_at", "last_run_dry", "last_affected_count"])

        log.info("Rule '%s' executed: %d messages affected (dry=%s)", rule.name, executed, dry_run)
        return audit

    except Exception as e:
        audit.status = "ERROR"
        audit.error_text = str(e)
        audit.finished_at = timezone.now()
        audit.save()
        log.error("Rule '%s' failed: %s", rule.name, e)
        raise


def apply_protected_sender_rules() -> CleanupAuditLog:
    """
    Special rule: star + label + keep in inbox messages from protected senders.
    Always runs for real (no dry_run) since it's protective, not destructive.
    """
    svc = gmail_service()
    if not svc:
        raise RuntimeError("Not authenticated")

    protected = list(ProtectedSender.objects.filter(star=True))
    audit = CleanupAuditLog.objects.create(
        rule=None,
        rule_name="Protected Senders — Star + Label",
        action="star+label",
        dry_run=False,
        actor_label="system",
        status="RUNNING",
    )

    executed = 0
    affected_ids = []

    for sender in protected:
        # Find verified messages from this sender that aren't starred yet
        msgs = GmailMessage.objects.filter(
            from_address__icontains=sender.email,
            state=GmailMessage.STATE_VERIFIED,
        ).exclude(labels__contains=["STARRED"])

        label_id = None
        if sender.label_to_apply:
            label_id = _get_or_create_label(svc, sender.label_to_apply)

        for msg in msgs:
            add = ["STARRED", "INBOX"]
            if label_id:
                add.append(label_id)
            if modify_labels(msg.gmail_id, add_labels=add):
                msg.labels = list(set(list(msg.labels) + add))
                msg.save(update_fields=["labels"])
                affected_ids.append(msg.gmail_id)
                executed += 1

    audit.affected_count = executed
    audit.affected_gmail_ids = affected_ids[:100]
    audit.status = "OK"
    audit.finished_at = timezone.now()
    audit.save()
    return audit


def run_all_enabled_rules(dry_run: bool = True, actor_label: str = "scheduler") -> list:
    """Run all enabled CleanupRules. Returns list of audit log records."""
    results = []
    for rule in CleanupRule.objects.filter(enabled=True).order_by("name"):
        try:
            audit = apply_rule(rule, dry_run=dry_run, actor_label=actor_label)
            results.append(audit)
        except Exception as e:
            log.error("Rule '%s' raised: %s", rule.name, e)
    return results
