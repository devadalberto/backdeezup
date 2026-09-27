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
from django.conf import settings as django_settings

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

# Phase 31 — weekly sampled integrity re-hash. Read-only, so default ON; set
# INTEGRITY_CHECK_ENABLED=0 to disable.
if getattr(django_settings, "INTEGRITY_CHECK_ENABLED", True):
    app.conf.beat_schedule["integrity-check"] = {
        "task": "core.tasks.task_integrity_check",
        "schedule": crontab(minute=0, hour=3, day_of_week=1),
        "options": {"expires": 3600},
    }

# Phase 33 — stale-backup notification. Off by default (NOTIFY_STALE_BACKUP_HOURS=0).
if getattr(django_settings, "NOTIFY_STALE_BACKUP_HOURS", 0):
    app.conf.beat_schedule["check-backup-freshness"] = {
        "task": "core.tasks.task_check_backup_freshness",
        "schedule": crontab(minute=15, hour="*"),
        "options": {"expires": 900},
    }

# Phase 37 — weekly "can I restore a file?" smoke test. Off by default
# (RESTORE_SMOKE_TEST_ENABLED=0); the dashboard button runs it on demand either way.
if getattr(django_settings, "RESTORE_SMOKE_TEST_ENABLED", False):
    app.conf.beat_schedule["restore-smoke-test"] = {
        "task": "core.tasks.task_restore_smoke_test",
        "schedule": crontab(minute=30, hour=4, day_of_week=1),
        "options": {"expires": 3600},
    }

# Phase 38 — weekly Postgres dump + prune. Off by default (DB_BACKUP_ENABLED=0);
# `make db-backup` / `make db-restore` work regardless of this flag.
if getattr(django_settings, "DB_BACKUP_ENABLED", False):
    app.conf.beat_schedule["db-backup"] = {
        "task": "core.tasks.task_db_backup",
        "schedule": crontab(minute=0, hour=4, day_of_week=0),
        "options": {"expires": 3600},
    }

app.conf.timezone = "America/Los_Angeles"
