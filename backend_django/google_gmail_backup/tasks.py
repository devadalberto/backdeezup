"""
Celery tasks for Gmail pipeline and cleanup.
These are the direct replacements for the APScheduler jobs in scheduler.py.
"""
import logging

from celery import shared_task

log = logging.getLogger(__name__)


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
            history_types=["messageAdded", "messageDeleted"],
        )
        added = 0
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
                GmailMessage.objects.filter(gmail_id=mid).update(state=GmailMessage.STATE_DELETED)

        if new_history_id:
            state.last_history_id = new_history_id
        state.last_incremental_at = timezone.now()
        state.save()
        log.info("task_gmail_incremental_sync: complete, %d new messages", added)
        return {"added": added}

    except Exception as exc:
        log.error("task_gmail_incremental_sync failed: %s", exc)
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
