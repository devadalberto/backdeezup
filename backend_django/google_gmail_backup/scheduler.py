"""
APScheduler jobs for periodic Gmail sync and cleanup.
All jobs are OFF by default — enable via Django Admin or settings.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler.jobstores import DjangoJobStore

log = logging.getLogger(__name__)
_scheduler = None


def job_gmail_incremental_sync():
    """Incremental Gmail sync — picks up new messages since last historyId."""
    try:
        from google_gmail_backup.services_gmail import (
            get_authenticated_email,
            list_history,
        )
        from google_gmail_backup.models import GmailMessage, GmailSyncState
        from django.utils import timezone

        email = get_authenticated_email()
        if not email:
            log.warning("Scheduler: not authenticated, skipping incremental sync")
            return

        state = GmailSyncState.objects.filter(email=email).first()
        if not state or not state.last_history_id:
            log.info("Scheduler: no historyId, skipping incremental sync")
            return

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
        log.info("Scheduler: incremental sync complete, %d new messages", added)
    except Exception as e:
        log.error("Scheduler: incremental sync failed: %s", e)


def job_apply_protected_senders():
    """Star + label messages from protected senders."""
    try:
        from google_gmail_backup.services_rules import apply_protected_sender_rules
        audit = apply_protected_sender_rules()
        log.info("Scheduler: protected senders applied, %d affected", audit.affected_count)
    except Exception as e:
        log.error("Scheduler: protected senders job failed: %s", e)


def job_run_cleanup_rules():
    """Run all enabled cleanup rules (dry_run=False)."""
    try:
        from google_gmail_backup.services_rules import run_all_enabled_rules
        results = run_all_enabled_rules(dry_run=False, actor_label="scheduler")
        total = sum(a.affected_count for a in results)
        log.info("Scheduler: cleanup rules ran, %d total affected", total)
    except Exception as e:
        log.error("Scheduler: cleanup rules job failed: %s", e)


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="America/Los_Angeles")
        _scheduler.add_jobstore(DjangoJobStore(), "default")
    return _scheduler


def start_scheduler():
    """Start the scheduler with default job schedule. Call from AppConfig.ready()."""
    scheduler = get_scheduler()
    if scheduler.running:
        return

    # Incremental sync: every 6 hours
    scheduler.add_job(
        job_gmail_incremental_sync,
        trigger=CronTrigger(hour="*/6"),
        id="gmail_incremental_sync",
        name="Gmail incremental sync",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Protected senders: every 6 hours (offset by 30 min)
    scheduler.add_job(
        job_apply_protected_senders,
        trigger=CronTrigger(hour="*/6", minute=30),
        id="protected_senders",
        name="Apply protected sender rules",
        replace_existing=True,
        misfire_grace_time=300,
    )

    # Cleanup rules: 3x per day at 06:00, 12:00, 18:00
    scheduler.add_job(
        job_run_cleanup_rules,
        trigger=CronTrigger(hour="6,12,18", minute=0),
        id="cleanup_rules",
        name="Run cleanup rules",
        replace_existing=True,
        misfire_grace_time=300,
    )

    scheduler.start()
    log.info("BackDeezUp scheduler started")
