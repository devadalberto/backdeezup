"""
Management command to seed protected senders and default cleanup rules.
Safe to run multiple times (uses get_or_create).

Usage:
    python manage.py seed_rules
    docker compose exec web python manage.py seed_rules
    make seed-rules
"""
from django.core.management.base import BaseCommand

from google_gmail_backup.models import CleanupRule, ProtectedSender


PROTECTED_SENDERS = [
    {
        "email": "mony.bello@gmail.com",
        "label_to_apply": "family",
        "star": True,
        "note": "Family",
    },
    {
        "email": "mony_littleowls@outlook.com",
        "label_to_apply": "family",
        "star": True,
        "note": "Family",
    },
    {
        "email": "virlochov@gmail.com",
        "label_to_apply": "family",
        "star": True,
        "note": "Family",
    },
    {
        "email": "julietvlhr@gmail.com",
        "label_to_apply": "family",
        "star": True,
        "note": "Family",
    },
]

CLEANUP_RULES = [
    {
        "name": "Trash Promotions older than 30 days",
        "description": "Emails categorized as Promotions older than 30 days.",
        "gmail_query": "category:promotions",
        "min_age_days": 30,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash Social notifications older than 30 days",
        "description": "Social notifications (Facebook, LinkedIn, etc.) older than 30 days.",
        "gmail_query": "category:social",
        "min_age_days": 30,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash Forums older than 60 days",
        "description": "Forum digests and mailing lists older than 60 days.",
        "gmail_query": "category:forums",
        "min_age_days": 60,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash Updates older than 30 days",
        "description": "Automated updates (receipts, confirmations) older than 30 days.",
        "gmail_query": "category:updates",
        "min_age_days": 30,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash newsletters older than 30 days",
        "description": "Emails containing unsubscribe links older than 30 days.",
        "gmail_query": "unsubscribe older_than:30d -is:starred -label:important",
        "min_age_days": 30,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash no-reply senders older than 60 days",
        "description": "Automated no-reply emails older than 60 days.",
        "gmail_query": "from:(no-reply OR noreply OR donotreply) -is:starred -label:important",
        "min_age_days": 60,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash mailing lists older than 60 days",
        "description": "List mail older than 60 days that is not starred.",
        "gmail_query": "list:* -is:starred -label:important",
        "min_age_days": 60,
        "action": CleanupRule.ACTION_TRASH,
    },
    {
        "name": "Trash spam folder",
        "description": "Messages sitting in the Spam folder.",
        "gmail_query": "in:spam",
        "min_age_days": 7,
        "action": CleanupRule.ACTION_TRASH,
    },
]


class Command(BaseCommand):
    help = "Seed protected senders and default cleanup rules (idempotent)"

    def handle(self, *args, **options):
        self.stdout.write("Seeding protected senders...")
        for data in PROTECTED_SENDERS:
            obj, created = ProtectedSender.objects.get_or_create(
                email=data["email"],
                defaults={
                    "label_to_apply": data["label_to_apply"],
                    "star": data["star"],
                    "note": data["note"],
                },
            )
            status = "created" if created else "exists"
            self.stdout.write(f"  {obj.email} [{status}]")

        self.stdout.write("\nSeeding cleanup rules...")
        for data in CLEANUP_RULES:
            obj, created = CleanupRule.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "gmail_query": data["gmail_query"],
                    "min_age_days": data["min_age_days"],
                    "action": data["action"],
                    "enabled": False,  # all rules OFF by default — review before enabling
                    "dry_run_default": True,
                },
            )
            status = "created" if created else "exists"
            self.stdout.write(f"  {obj.name} [{status}]")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {len(PROTECTED_SENDERS)} protected senders, "
            f"{len(CLEANUP_RULES)} cleanup rules seeded.\n"
            "Rules are disabled by default. Review in /admin/google_gmail_backup/cleanuprule/\n"
            "Run dry-runs first: POST /api/gmail/rules/run-all?dry_run=true"
        ))
