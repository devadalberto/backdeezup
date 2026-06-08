"""
Celery application for BackDeezUp.
Replaces APScheduler — periodic tasks run in a dedicated celery worker + celery beat.

Start workers:
    docker compose exec celery celery -A celery_app worker -l info
    docker compose exec celerybeat celery -A celery_app beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("backdeezup")

# Read config from Django settings, CELERY_* namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


# ── Periodic schedule (mirrors the old APScheduler schedule) ─────────────────

app.conf.beat_schedule = {
    "gmail-incremental-sync": {
        "task": "google_gmail_backup.tasks.task_gmail_incremental_sync",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"expires": 300},
    },
    "apply-protected-senders": {
        "task": "google_gmail_backup.tasks.task_apply_protected_senders",
        "schedule": crontab(minute=30, hour="*/6"),
        "options": {"expires": 300},
    },
    "run-cleanup-rules": {
        "task": "google_gmail_backup.tasks.task_run_cleanup_rules",
        "schedule": crontab(minute=0, hour="6,12,18"),
        "options": {"expires": 300},
    },
}
app.conf.timezone = "America/Los_Angeles"
