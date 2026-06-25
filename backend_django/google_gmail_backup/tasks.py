"""
Celery tasks for Gmail pipeline and cleanup.
These are the direct replacements for the APScheduler jobs in scheduler.py.
"""
import logging

from celery import shared_task

from .schemas import snapshot_from_message

log = logging.getLogger(__name__)


def _record_task_failure(task_name: str, exc: Exception) -> None:
    """Record task failure on all GmailSyncState rows and fire Sentry if configured."""
    try:
        from .models import GmailSyncState
        from django.utils import timezone
        # Update all sync state rows — in single-account setup there's only one
        GmailSyncState.objects.update(
            last_error=f"[{task_name}] {str(exc)[:900]}",
            last_error_at=timezone.now(),
        )
    except Exception:
        pass
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


@shared_task(bind=True, max_retries=3, default_retry_delay=120, name="google_gmail_backup.tasks.task_gmail_incremental_sync")
def task_gmail_incremental_sync(self):
    """Incremental Gmail sync — picks up new messages since last historyId."""
    try:
        from .services_gmail import get_authenticated_email, list_history
        from .models import GmailMessage, GmailSyncState
        from django.utils import timezone

        email = get_authenticated_email()
        if not email:
            log.warning("task_gmail_incremental_sync: not authenticated, skipping")
            return {"skipped": True, "reason": "not authenticated"}

        state = GmailSyncState.objects.filter(email=email).first()
        if not state or not state.last_history_id:
            log.info("task_gmail_incremental_sync: no historyId, skipping")
            return {"skipped": True, "reason": "no historyId"}

        records, new_history_id = list_history(
            state.last_history_id,
            history_types=["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"],
        )
        added = 0
        soft_deleted = 0
        restored = 0

        for record in records:
            for msg_added in record.get("messagesAdded", []):
                mid = msg_added["message"]["id"]
                GmailMessage.objects.get_or_create(
                    gmail_id=mid,
                    defaults={"thread_id": "", "account_email": email,
                              "state": GmailMessage.STATE_DISCOVERED},
                )
                added += 1

            for msg_del in record.get("messagesDeleted", []):
                mid = msg_del["message"]["id"]
                msg = GmailMessage.objects.filter(gmail_id=mid).first()
                if msg and msg.state != GmailMessage.STATE_DELETED:
                    if not msg.metadata_snapshot:
                        msg.metadata_snapshot = snapshot_from_message(msg)
                    msg.state = GmailMessage.STATE_DELETED
                    msg.deleted_at = msg.deleted_at or timezone.now()
                    msg.deletion_source = msg.deletion_source or "gmail_sync"
                    msg.save(update_fields=["state", "deleted_at", "deletion_source", "metadata_snapshot"])

            # Detect trash/untrash via label changes
            for label_added in record.get("labelsAdded", []):
                msg_data = label_added.get("message", {})
                mid = msg_data.get("id")
                label_ids = label_added.get("labelIds", [])
                if "TRASH" in label_ids and mid:
                    msg = GmailMessage.objects.filter(gmail_id=mid).first()
                    if msg and msg.state in (GmailMessage.STATE_VERIFIED, GmailMessage.STATE_DOWNLOADED):
                        msg.state = GmailMessage.STATE_SOFT_DELETED
                        msg.deleted_at = timezone.now()
                        msg.deletion_source = "gmail_user"
                        msg.metadata_snapshot = snapshot_from_message(msg)
                        msg.save(update_fields=["state", "deleted_at", "deletion_source", "metadata_snapshot"])
                        soft_deleted += 1

            for label_removed in record.get("labelsRemoved", []):
                msg_data = label_removed.get("message", {})
                mid = msg_data.get("id")
                label_ids = label_removed.get("labelIds", [])
                if "TRASH" in label_ids and mid:
                    msg = GmailMessage.objects.filter(gmail_id=mid, state=GmailMessage.STATE_SOFT_DELETED).first()
                    if msg:
                        msg.state = GmailMessage.STATE_VERIFIED
                        msg.deleted_at = None
                        msg.deletion_source = ""
                        msg.metadata_snapshot = {}
                        msg.save(update_fields=["state", "deleted_at", "deletion_source", "metadata_snapshot"])
                        restored += 1

        if new_history_id:
            state.last_history_id = new_history_id
        state.last_incremental_at = timezone.now()
        state.save()
        log.info("task_gmail_incremental_sync: complete, added=%d soft_deleted=%d restored=%d", added, soft_deleted, restored)
        return {"added": added, "soft_deleted": soft_deleted, "restored": restored}

    except Exception as exc:
        log.error("task_gmail_incremental_sync failed: %s", exc)
        _record_task_failure("incremental_sync", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, name="google_gmail_backup.tasks.task_apply_protected_senders")
def task_apply_protected_senders(self):
    """Star + label messages from protected senders."""
    try:
        from .services_rules import apply_protected_sender_rules
        audit = apply_protected_sender_rules()
        log.info("task_apply_protected_senders: %d affected", audit.affected_count)
        return {"affected": audit.affected_count}
    except Exception as exc:
        log.error("task_apply_protected_senders failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=60, name="google_gmail_backup.tasks.task_run_cleanup_rules")
def task_run_cleanup_rules(self):
    """Run all enabled cleanup rules."""
    try:
        from .services_rules import run_all_enabled_rules
        results = run_all_enabled_rules(dry_run=False, actor_label="celery")
        total = sum(a.affected_count for a in results)
        log.info("task_run_cleanup_rules: %d total affected across %d rules", total, len(results))
        return {"affected": total, "rules_run": len(results)}
    except Exception as exc:
        log.error("task_run_cleanup_rules failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(name="google_gmail_backup.tasks.task_gmail_download_batch")
def task_gmail_download_batch(limit: int = 500, workers: int = 10):
    """Trigger a download batch — useful for on-demand pipeline from web UI."""
    import subprocess
    import sys
    result = subprocess.run(
        [sys.executable, "manage.py", "gmail_pipeline", "download",
         f"--limit={limit}", f"--workers={workers}"],
        capture_output=True, text=True,
        cwd="/app/backend_django",
    )
    return {"stdout": result.stdout[-2000:], "returncode": result.returncode}


@shared_task(bind=True, max_retries=1, default_retry_delay=300, name="google_gmail_backup.tasks.task_gmail_reconcile")
def task_gmail_reconcile(self):
    """Compare local VERIFIED messages against live Gmail — mark missing as SOFT_DELETED.

    Uses list diff strategy: fetches all live Gmail IDs (~50 API calls) then diffs
    against local DB — avoids per-message API calls (was 25,000 calls → ~7h runtime).
    Only calls messages.get() for IDs that exist locally but not in Gmail list.
    """
    try:
        from .services_gmail import gmail_service
        from .models import GmailMessage
        from django.utils import timezone

        svc = gmail_service()
        if not svc:
            log.warning("task_gmail_reconcile: not authenticated, skipping")
            return {"skipped": True, "reason": "not authenticated"}

        # Step 1: get all local VERIFIED/DOWNLOADED IDs
        local_ids = set(
            GmailMessage.objects.filter(
                state__in=[GmailMessage.STATE_VERIFIED, GmailMessage.STATE_DOWNLOADED]
            ).values_list("gmail_id", flat=True)
        )
        log.info("task_gmail_reconcile: %d local messages to check", len(local_ids))

        # Step 2: fetch all live Gmail IDs using messages.list (not messages.get)
        # Excludes trash/spam by default — gives us what's in normal labels
        live_ids = set()
        page_token = None
        pages = 0
        while True:
            params = {"userId": "me", "maxResults": 500, "fields": "messages(id),nextPageToken"}
            if page_token:
                params["pageToken"] = page_token
            res = svc.users().messages().list(**params).execute()
            for m in res.get("messages", []):
                live_ids.add(m["id"])
            page_token = res.get("nextPageToken")
            pages += 1
            if not page_token:
                break
        log.info("task_gmail_reconcile: fetched %d live IDs in %d pages", len(live_ids), pages)

        # Step 3: diff — IDs in local DB but NOT in live Gmail list
        missing_ids = local_ids - live_ids
        log.info("task_gmail_reconcile: %d potentially missing (may be in archive/sent/spam)", len(missing_ids))

        # Step 4: for missing IDs, call messages.get to confirm they're truly gone
        # (they may be in Archive, Sent, Spam — just not in the default list)
        import time
        soft_deleted = 0
        confirmed = len(local_ids) - len(missing_ids)
        errors = 0
        now = timezone.now()

        BATCH_SIZE = 50
        missing_list = list(missing_ids)
        for i in range(0, len(missing_list), BATCH_SIZE):
            batch = missing_list[i:i + BATCH_SIZE]
            for gmail_id in batch:
                try:
                    result = svc.users().messages().get(
                        userId="me", id=gmail_id, format="minimal",
                        fields="id,labelIds",
                    ).execute()
                    labels = result.get("labelIds", [])
                    if "TRASH" in labels:
                        _mark_soft_deleted(gmail_id, "gmail_user", now)
                        soft_deleted += 1
                    else:
                        confirmed += 1  # exists in archive/sent/other label
                except Exception as exc:
                    exc_str = str(exc)
                    if "404" in exc_str or "notFound" in exc_str:
                        _mark_soft_deleted(gmail_id, "gmail_sync", now)
                        soft_deleted += 1
                    else:
                        log.warning("task_gmail_reconcile: error checking %s: %s", gmail_id, exc)
                        errors += 1
            if i + BATCH_SIZE < len(missing_list):
                time.sleep(0.1)  # rate limit only on the targeted subset

        log.info(
            "task_gmail_reconcile: confirmed=%d soft_deleted=%d errors=%d "
            "(list_pages=%d, targeted_checks=%d)",
            confirmed, soft_deleted, errors, pages, len(missing_ids),
        )
        return {"confirmed": confirmed, "soft_deleted": soft_deleted, "errors": errors,
                "list_pages": pages, "targeted_checks": len(missing_ids)}

    except Exception as exc:
        log.error("task_gmail_reconcile failed: %s", exc)
        _record_task_failure("task_gmail_reconcile", exc)
        raise self.retry(exc=exc)


def _mark_soft_deleted(gmail_id: str, source: str, now) -> None:
    """Mark a single GmailMessage as SOFT_DELETED with metadata snapshot."""
    from .models import GmailMessage
    try:
        msg = GmailMessage.objects.get(gmail_id=gmail_id)
        msg.state = GmailMessage.STATE_SOFT_DELETED
        msg.deleted_at = now
        msg.deletion_source = source
        if not msg.metadata_snapshot:
            msg.metadata_snapshot = snapshot_from_message(msg)
        msg.save(update_fields=["state", "deleted_at", "deletion_source", "metadata_snapshot"])
    except GmailMessage.DoesNotExist:
        pass


@shared_task(name="google_gmail_backup.tasks.task_purge_expired_soft_deletes")
def task_purge_expired_soft_deletes():
    """Purge SOFT_DELETED records older than 90 days — set state to DELETED, keep .eml on disk."""
    from datetime import timedelta
    from .models import GmailMessage
    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=GmailMessage.RETENTION_DAYS)
    expired = GmailMessage.objects.filter(
        state=GmailMessage.STATE_SOFT_DELETED,
        deleted_at__lte=cutoff,
    )
    count = expired.count()

    for msg in expired.iterator(chunk_size=500):
        if not msg.metadata_snapshot:
            msg.metadata_snapshot = snapshot_from_message(msg)
            msg.save(update_fields=["metadata_snapshot"])

    expired.update(state=GmailMessage.STATE_DELETED)
    log.info("task_purge_expired_soft_deletes: purged %d records", count)
    return {"purged": count}
