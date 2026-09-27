"""
Cleanup rules engine.
All actions support dry_run=True (default) — nothing touches Gmail until dry_run=False.
Protected senders are always skipped.
Every execution is logged to CleanupAuditLog.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Max

from .schemas import snapshot_from_message
from django.utils import timezone

from .models import CleanupAuditLog, CleanupRule, GmailMessage, ProtectedSender, RuleCondition
from .services_gmail import (
    batch_modify_labels,
    gmail_service,
    modify_labels,
    trash_message,
    untrash_message,
)

log = logging.getLogger(__name__)


def is_cleanup_paused() -> bool:
    """Phase 34 global pause switch. Only gates REAL runs — dry runs are harmless."""
    return bool(getattr(settings, "CLEANUP_PAUSED", False))


def dry_run_confirmation_error(rule: CleanupRule, confirm_count) -> str | None:
    """Phase 34 gate for the new Execute UI path only.

    Existing callers (run_all_enabled_rules / `make cleanup-run` / Beat) are NOT
    subject to this — they only honor CLEANUP_PAUSED. Returns an error message,
    or None when the execute request may proceed.
    """
    if not getattr(settings, "CLEANUP_REQUIRE_DRY_RUN", True):
        return None
    if not rule.last_dry_run_at:
        return "A dry run is required before executing this rule."
    max_age = timedelta(hours=getattr(settings, "CLEANUP_DRY_RUN_MAX_AGE_HOURS", 24))
    if timezone.now() - rule.last_dry_run_at > max_age:
        return "The last dry run is more than 24h old — run a new dry run first."
    if confirm_count != rule.last_dry_run_count:
        return f"Confirmation count mismatch: expected {rule.last_dry_run_count}."
    return None


def _sync_attachment_guard_condition(rule: CleanupRule) -> None:
    """Phase 34: keep a RuleCondition row in sync with never_delete_with_attachments,
    reusing the existing condition model/compiler instead of a one-off filter string."""
    existing = rule.conditions.filter(
        field=RuleCondition.FIELD_HAS_ATTACH, operator=RuleCondition.OP_NOT_EQUALS,
    ).first()
    if rule.never_delete_with_attachments:
        if not existing:
            next_order = (rule.conditions.aggregate(Max("order"))["order__max"] or 0) + 1
            RuleCondition.objects.create(
                rule=rule, order=next_order, field=RuleCondition.FIELD_HAS_ATTACH,
                operator=RuleCondition.OP_NOT_EQUALS, value="", logic=RuleCondition.LOGIC_AND,
            )
    elif existing:
        existing.delete()


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


def _notify_cleanup_executed(rule_name: str, action: str, affected: int) -> None:
    """Phase 33 event: a real (non-dry-run) rule execution. Never raises."""
    try:
        from core import notify
        notify.send(
            "cleanup_executed",
            f"Cleanup rule '{rule_name}' executed",
            f"Action '{action}' affected {affected} message(s).",
        )
    except Exception:
        pass


def apply_rule(rule: CleanupRule, dry_run: bool = True, actor_label: str = "system") -> CleanupAuditLog:
    """
    Apply a CleanupRule. Returns a CleanupAuditLog record.
    Protected senders are always skipped regardless of rule.
    """
    if not dry_run and is_cleanup_paused():
        log.info("Cleanup paused (CLEANUP_PAUSED) — skipping real run of rule '%s' (actor=%s)", rule.name, actor_label)
        return CleanupAuditLog.objects.create(
            rule=rule, rule_name=rule.name, action=rule.action, dry_run=dry_run,
            actor_label=actor_label, status="PAUSED", finished_at=timezone.now(),
        )

    _sync_attachment_guard_condition(rule)

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

        with transaction.atomic():
            # select_for_update requires an open transaction — prevents concurrent
            # rule runs from double-trashing the same messages.
            # Exclude messages processed within last 24h (idempotency guard for Celery retries).
            from datetime import timedelta as _td
            recent_cutoff = timezone.now() - _td(hours=24)
            qs = GmailMessage.objects.select_for_update(skip_locked=True).filter(
                state=GmailMessage.STATE_VERIFIED,
                date__lte=cutoff,
            ).exclude(deleted_at__gte=recent_cutoff)

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

            # Exclude protected senders — use indexed from_email_normalized (O(1) vs ILIKE O(n))
            if rule.respect_protected_senders and protected:
                normalized = {e.lower() for e in protected}
                qs = qs.exclude(from_email_normalized__in=normalized)
            if rule.never_delete_with_attachments:
                qs = qs.exclude(has_attachments=True)
            if dry_run:
                # Dry-run: count from DB only (no Gmail API, fast)
                total_count = qs.count()
                sample_subjects = [m.subject[:80] for m in qs[:10]]
                audit.affected_count = total_count
                audit.affected_gmail_ids = list(qs.values_list("gmail_id", flat=True)[:100])
                audit.affected_ids_truncated = total_count > 100
                audit.sample_subjects = sample_subjects
                audit.status = "DRY_RUN"
                audit.finished_at = timezone.now()
                audit.save()
                rule.last_dry_run_count = total_count
                rule.last_dry_run_at = timezone.now()
                rule.save(update_fields=["last_dry_run_count", "last_dry_run_at"])
                return audit

            # Execute — batch loop, no hard cap (max 50 iterations = 50k messages safety)
            svc = gmail_service()
            if not svc:
                raise RuntimeError("Not authenticated — run make auth first")

            executed = 0
            sample_subjects = []
            BATCH = 1000

            for _iteration in range(50):
                batch = list(qs[:BATCH])
                if not batch:
                    break
                if not sample_subjects:
                    sample_subjects = [m.subject[:80] for m in batch[:10]]

                if rule.action == CleanupRule.ACTION_TRASH:
                    trashed_ids = []
                    for msg in batch:
                        if not msg.metadata_snapshot:
                            msg.metadata_snapshot = snapshot_from_message(msg)
                            msg.save(update_fields=["metadata_snapshot"])
                        if trash_message(msg.gmail_id):
                            trashed_ids.append(msg.gmail_id)
                            executed += 1
                    if trashed_ids:
                        GmailMessage.objects.filter(gmail_id__in=trashed_ids).update(
                            state=GmailMessage.STATE_TRASHED,
                            deleted_at=timezone.now(),
                            deletion_source="cleanup_rule",
                        )

                elif rule.action == CleanupRule.ACTION_STAR:
                    for msg in batch:
                        if modify_labels(msg.gmail_id, add_labels=["STARRED"]):
                            if "STARRED" not in msg.labels:
                                msg.labels = list(msg.labels) + ["STARRED"]
                                msg.save(update_fields=["labels"])
                            executed += 1

                elif rule.action == CleanupRule.ACTION_LABEL:
                    label_id = _get_or_create_label(svc, rule.label_name)
                    for msg in batch:
                        if modify_labels(msg.gmail_id, add_labels=[label_id]):
                            executed += 1

                elif rule.action == CleanupRule.ACTION_ARCHIVE:
                    for msg in batch:
                        if modify_labels(msg.gmail_id, remove_labels=["INBOX"]):
                            executed += 1

                if len(batch) < BATCH:
                    break  # last batch processed

            audit.affected_count = executed
            audit.sample_subjects = sample_subjects
            audit.status = "OK"
            audit.finished_at = timezone.now()
            audit.save()

            rule.last_run_at = timezone.now()
            rule.last_run_dry = False
            rule.last_affected_count = executed
            rule.save(update_fields=["last_run_at", "last_run_dry", "last_affected_count"])

            log.info("Rule '%s' executed: %d messages affected (dry=%s)", rule.name, executed, dry_run)
            _notify_cleanup_executed(rule.name, rule.action, executed)
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

    # Use indexed from_email_normalized for O(1) exact match instead of ILIKE scans
    protected_emails = {s.email.lower() for s in protected}
    all_candidate_msgs = list(
        GmailMessage.objects.filter(
            from_email_normalized__in=protected_emails,
            state=GmailMessage.STATE_VERIFIED,
        ).exclude(labels__contains=["STARRED"])
    )
    # Group by sender using normalized field (exact match, indexed)
    candidate_by_email: dict = {}
    for msg in all_candidate_msgs:
        for sender in protected:
            if msg.from_email_normalized == sender.email.lower():
                candidate_by_email.setdefault(sender.email, []).append(msg)
                break

    for sender in protected:
        msgs = candidate_by_email.get(sender.email, [])
        if not msgs:
            continue

        if not msgs:
            continue

        label_id = None
        if sender.label_to_apply:
            label_id = _get_or_create_label(svc, sender.label_to_apply)

        add = ["STARRED", "INBOX"]
        if label_id:
            add.append(label_id)

        msg_ids = [m.gmail_id for m in msgs]
        # Single batchModify call per sender — O(1) API calls instead of O(n)
        if batch_modify_labels(msg_ids, add_labels=add):
            GmailMessage.objects.filter(gmail_id__in=msg_ids).update(
                labels=add  # approximate — full label merge handled at next sync
            )
            affected_ids.extend(msg_ids)
            executed += len(msg_ids)
            log.info("Protected sender %s: starred %d messages", sender.email, len(msg_ids))

    audit.affected_count = executed
    audit.affected_gmail_ids = affected_ids[:100]
    audit.status = "OK"
    audit.finished_at = timezone.now()
    audit.save()
    return audit


def run_all_enabled_rules(dry_run: bool = True, actor_label: str = "scheduler") -> list:
    """Run all enabled CleanupRules. Returns list of audit log records.

    Uses a Redis lock to prevent concurrent executions from two callers.
    Raises RuntimeError if another execution is already running.
    """
    from django.core.cache import cache

    if not dry_run and is_cleanup_paused():
        log.info("Cleanup paused (CLEANUP_PAUSED) — run_all_enabled_rules no-op (actor=%s)", actor_label)
        return []

    LOCK_KEY = "backdeezup:cleanup_rules_running"
    LOCK_TTL = 1800  # 30 minutes max — prevents stuck lock from blocking forever

    if not dry_run:
        # Acquire Redis lock — nx=True means only set if key doesn't exist
        acquired = cache.add(LOCK_KEY, actor_label, LOCK_TTL)
        if not acquired:
            running_by = cache.get(LOCK_KEY, "unknown")
            raise RuntimeError(
                f"Cleanup rules already running (started by: {running_by}). "
                "Wait for it to finish or check /admin/google_gmail_backup/cleanupauditlog/."
            )
    try:
        results = []
        for rule in CleanupRule.objects.filter(enabled=True).order_by("name"):
            try:
                audit = apply_rule(rule, dry_run=dry_run, actor_label=actor_label)
                results.append(audit)
            except Exception as e:
                log.error("Rule '%s' raised: %s", rule.name, e)
        return results
    finally:
        if not dry_run:
            cache.delete(LOCK_KEY)


# ── Undo (Phase 35) ────────────────────────────────────────────────────────────

def undo_audit_log(audit: CleanupAuditLog, actor_label: str = "api") -> dict:
    """Restore the messages one CleanupAuditLog run sent to Trash.

    Only Trash actions inside Gmail's retention window are restorable. Permanent
    deletes, dry runs, and non-Trash actions are reported as not applicable rather
    than attempted. Failures are reported per message id -- one bad id never aborts
    the rest of the batch. Only the (up to 100) ids stored on the audit row can be
    restored; runs with affected_ids_truncated=True will only partially undo.
    """
    if audit.dry_run:
        return {"restored": 0, "failed": [], "skipped": True, "reason": "Dry run made no changes -- nothing to undo."}
    if audit.undone_at:
        return {"restored": 0, "failed": [], "skipped": True, "reason": "This run has already been undone."}
    if audit.action == "permanent_delete":
        return {"restored": 0, "failed": [], "skipped": True, "reason": "Permanently deleted messages are not restorable."}
    if audit.action != CleanupRule.ACTION_TRASH:
        return {"restored": 0, "failed": [], "skipped": True,
                "reason": f"Undo is only defined for Trash actions (this run was '{audit.action}')."}

    svc = gmail_service()
    if not svc:
        raise RuntimeError("Not authenticated — run make auth first")

    restored, failed = [], []
    for gmail_id in audit.affected_gmail_ids:
        if untrash_message(gmail_id):
            restored.append(gmail_id)
        else:
            failed.append(gmail_id)

    if restored:
        GmailMessage.objects.filter(gmail_id__in=restored).update(
            state=GmailMessage.STATE_VERIFIED, deleted_at=None, deletion_source="",
        )

    audit.undone_at = timezone.now()
    audit.save(update_fields=["undone_at"])

    undo_log = CleanupAuditLog.objects.create(
        rule=audit.rule, rule_name=f"Undo: {audit.rule_name}", action="untrash",
        dry_run=False, actor_label=actor_label,
        status="OK" if not failed else "PARTIAL",
        affected_count=len(restored), affected_gmail_ids=restored[:100],
        finished_at=timezone.now(),
    )
    log.info("Undo of audit log %s: %d restored, %d failed", audit.id, len(restored), len(failed))

    return {
        "restored": len(restored), "failed": failed, "skipped": False,
        "undo_audit_id": undo_log.id,
        "truncated_note": (
            "Only the first 100 message ids were stored on the original run -- "
            "more than 100 were affected, so this undo is partial."
        ) if audit.affected_ids_truncated else "",
    }


# ── Protect sender (Phase 35) ───────────────────────────────────────────────────

def protect_sender(email: str, label_to_apply: str = "", star: bool = False, note: str = "") -> ProtectedSender:
    """get_or_create a ProtectedSender. Idempotent -- calling it again for the same
    email is a no-op that returns the existing row."""
    return ProtectedSender.objects.get_or_create(
        email=email.strip().lower(),
        defaults={"label_to_apply": label_to_apply, "star": star, "note": note},
    )[0]
