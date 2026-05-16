import os

from django.apps import AppConfig


class GoogleGmailBackupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "google_gmail_backup"
    verbose_name = "Gmail Backup"

    def ready(self):
        # Only start scheduler in the main process, not during migrations/tests
        if os.environ.get("BACKDEEZUP_SCHEDULER", "0") == "1":
            from .scheduler import start_scheduler
            start_scheduler()
