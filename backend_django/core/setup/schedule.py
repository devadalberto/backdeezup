"""Writes the SAME Beat entries the seed uses (Phase 30 step 5).

``celery_app.py``'s static ``beat_schedule`` dict is what django-celery-beat's
``DatabaseScheduler`` (CELERY_BEAT_SCHEDULER, config/settings.py) seeds into
the database on first Beat startup, as PeriodicTask rows with these same
names. This just re-points those same three rows at a simpler daily/weekly
preset chosen in the wizard, in TIME_ZONE, instead of writing new entries.
"""
from django.conf import settings

BEAT_TASK_NAMES = {
    "gmail-incremental-sync": "google_gmail_backup.tasks.task_gmail_incremental_sync",
    "apply-protected-senders": "google_gmail_backup.tasks.task_apply_protected_senders",
    "run-cleanup-rules": "google_gmail_backup.tasks.task_run_cleanup_rules",
}

PRESET_DAY_OF_WEEK = {"daily": "*", "weekly": "1"}  # 1 = Monday


def apply_schedule(preset, hour, minute):
    from django_celery_beat.models import CrontabSchedule, PeriodicTask

    if preset not in PRESET_DAY_OF_WEEK:
        raise ValueError(f"Unknown schedule preset '{preset}'")

    crontab, _ = CrontabSchedule.objects.get_or_create(
        minute=str(minute), hour=str(hour), day_of_week=PRESET_DAY_OF_WEEK[preset],
        day_of_month="*", month_of_year="*", timezone=settings.TIME_ZONE,
    )
    for name, task in BEAT_TASK_NAMES.items():
        PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "task": task, "crontab": crontab,
                "interval": None, "solar": None, "clocked": None,
                "enabled": True, "one_off": False,
            },
        )
    return crontab
