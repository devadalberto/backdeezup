"""
Setup Gmail push notifications via Google Cloud Pub/Sub.

Usage:
    docker compose exec web python manage.py setup_gmail_watch
    make gmail-watch-setup

The watch expires every 7 days. Renew via the Celery Beat task
task_renew_gmail_watch or run this command again.

Prerequisites:
    1. Create Pub/Sub topic: backdeezup-gmail-push
    2. Grant Gmail service account publish rights to the topic
    3. Create push subscription pointing to https://<host>/api/gmail/push
"""
import logging

from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Setup or renew Gmail push notification watch via Pub/Sub"

    def add_arguments(self, parser):
        parser.add_argument(
            "--topic",
            default="",
            help="Pub/Sub topic name (e.g. projects/my-project/topics/backdeezup-gmail-push)",
        )

    def handle(self, *args, **options):
        from decouple import config
        from google_media_backup.services_google import _load_creds, _save_creds
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        topic = options["topic"] or config("GMAIL_PUBSUB_TOPIC", default="")
        if not topic:
            self.stdout.write(self.style.ERROR(
                "No Pub/Sub topic specified. Pass --topic or set GMAIL_PUBSUB_TOPIC in .env\n"
                "Format: projects/<project-id>/topics/<topic-name>"
            ))
            return

        creds = _load_creds()
        if not creds:
            self.stdout.write(self.style.ERROR("Not authenticated. Run: make auth"))
            return
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_creds(creds)

        svc = build("gmail", "v1", credentials=creds)
        try:
            result = svc.users().watch(
                userId="me",
                body={
                    "topicName": topic,
                    "labelIds": ["INBOX"],
                    "labelFilterBehavior": "INCLUDE",
                },
            ).execute()
            expiry = result.get("expiration", "unknown")
            history_id = result.get("historyId", "unknown")
            self.stdout.write(self.style.SUCCESS(
                f"Gmail watch set up successfully.\n"
                f"  historyId: {history_id}\n"
                f"  Expiry (ms since epoch): {expiry}\n"
                f"  Watch expires in ~7 days. Renew with: make gmail-watch-setup"
            ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Failed to set up watch: {exc}"))
