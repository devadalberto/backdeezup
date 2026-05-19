from django.apps import AppConfig


class GoogleGmailBackupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "google_gmail_backup"
    verbose_name = "Gmail Backup"

    def ready(self):
        # Import tasks so Celery autodiscover finds them
        import google_gmail_backup.tasks  # noqa: F401
