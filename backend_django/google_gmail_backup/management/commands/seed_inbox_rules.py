"""
Seed inbox-specific cleanup rules based on observed inbox content.
Safe to run multiple times — uses get_or_create on rule name.

Usage:
    docker compose exec web python manage.py seed_inbox_rules
    make seed-inbox-rules
"""
from django.core.management.base import BaseCommand
from google_gmail_backup.models import CleanupRule

INBOX_RULES = [
    # ── Banking / financial statements → archive (keep but clear inbox) ──
    {
        "name": "Archive bank statements and financial alerts",
        "description": "Banco BICE, Tarjeta Lider, La Polar, generic account statements. Archive not trash.",
        "gmail_query": (
            "from:(bice.cl OR lider.cl OR lapolar.cl OR bancoestado.cl OR cmrfalabella.com) "
            "OR subject:(\"estado de cuenta\" OR \"transferencia\" OR \"tarjeta\" OR \"tu saldo\")"
        ),
        "min_age_days": 0,
        "action": CleanupRule.ACTION_ARCHIVE,
    },
    # ── Neighborhood / Nextdoor → label ───────────────────────────────────
    {
        "name": "Label neighborhood notifications (Nextdoor)",
        "description": "Woodhaven / Nextdoor neighborhood posts.",
        "gmail_query": "from:(nextdoor.com OR ss.email.nextdoor.com)",
        "min_age_days": 0,
        "action": CleanupRule.ACTION_LABEL,
        "label_name": "neighborhood",
    },
    # ── CEO scam / phishing → trash immediately ───────────────────────────
    {
        "name": "Trash CEO meeting scam emails",
        "description": "Classic phishing pattern — 'Meeting with CEO' from unknown senders.",
        "gmail_query": (
            "subject:(\"meeting with CEO\" OR \"CEO wants to meet\" OR \"urgent request from CEO\" "
            "OR \"message from CEO\") -from:(anthropic.com OR google.com OR microsoft.com)"
        ),
        "min_age_days": 0,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── Apple Developer → archive ────────────────────────────────────────
    {
        "name": "Archive Apple Developer emails",
        "description": "WWDC, App Store, developer.apple.com notifications.",
        "gmail_query": "from:(developer.apple.com OR apple.com) subject:(developer OR WWDC OR \"App Store\")",
        "min_age_days": 7,
        "action": CleanupRule.ACTION_ARCHIVE,
    },
    # ── Food delivery / loyalty rewards → trash ───────────────────────────
    {
        "name": "Trash food delivery and loyalty reward emails",
        "description": "Jimmy John's, Temu, and similar retail/loyalty spam.",
        "gmail_query": (
            "from:(jimmyjohns.com OR temu.com OR doordash.com OR ubereats.com OR grubhub.com) "
            "-subject:(receipt OR order confirmation OR delivery)"
        ),
        "min_age_days": 3,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── USPS / shipping notifications → archive after delivery ───────────
    {
        "name": "Archive USPS and shipping notifications",
        "description": "Tracking and delivery notifications — archive once delivered.",
        "gmail_query": (
            "from:(usps.com OR informeddelivery.usps.com OR ups.com OR fedex.com OR dhl.com) "
            "subject:(delivered OR \"out for delivery\" OR tracking)"
        ),
        "min_age_days": 1,
        "action": CleanupRule.ACTION_ARCHIVE,
    },
    # ── Pharma / medical marketing → trash ───────────────────────────────
    {
        "name": "Trash pharmaceutical marketing emails",
        "description": "Grünenthal, pharma marketing — not medical records.",
        "gmail_query": "from:(grunenthal.com OR grünenthal.com)",
        "min_age_days": 0,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── Steam / gaming promotions → trash ────────────────────────────────
    {
        "name": "Trash Steam and gaming promotions",
        "description": "Steam sale notifications, wishlist updates.",
        "gmail_query": "from:(steampowered.com OR store.steampowered.com) -subject:receipt",
        "min_age_days": 3,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── Instagram / social DM notifications → trash ──────────────────────
    {
        "name": "Trash Instagram notification emails",
        "description": "Instagram DM and activity notifications — check app instead.",
        "gmail_query": "from:(facebookmail.com OR instagram.com) subject:(messaged OR \"new message\" OR \"unread\")",
        "min_age_days": 1,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── Powerball / lottery → trash ──────────────────────────────────────
    {
        "name": "Trash lottery and sweepstakes emails",
        "description": "Powerball drawing results, lottery notifications.",
        "gmail_query": "from:(powerball.com OR lotteryusa.com) OR subject:(\"Powerball\" OR \"lottery numbers\" OR \"winning numbers\")",
        "min_age_days": 0,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── News digests → trash after 7 days ────────────────────────────────
    {
        "name": "Trash news digest emails older than 7 days",
        "description": "Daily/breaking news digests (Happy News, Daily Hist., Morning Brew, etc.)",
        "gmail_query": (
            "from:(morningbrew.com OR happynewspaper.com OR thedailydigest.com) "
            "OR subject:(\"Daily Digest\" OR \"Breaking:\" OR \"Today in History\" OR \"One Of America\")"
        ),
        "min_age_days": 7,
        "action": CleanupRule.ACTION_TRASH,
    },
    # ── WOM / telecom marketing → trash ──────────────────────────────────
    {
        "name": "Trash WOM and telecom marketing",
        "description": "WOM Mobile promotions and debt alerts.",
        "gmail_query": "from:(wom.cl OR womcl.com OR wommovil.cl)",
        "min_age_days": 0,
        "action": CleanupRule.ACTION_TRASH,
    },
]


class Command(BaseCommand):
    help = "Seed inbox-specific cleanup rules (idempotent)"

    def handle(self, *args, **options):
        created_count = skipped_count = 0

        for data in INBOX_RULES:
            kwargs = {
                "description": data["description"],
                "gmail_query": data["gmail_query"],
                "min_age_days": data["min_age_days"],
                "action": data["action"],
                "enabled": True,   # these are well-scoped — start enabled
                "dry_run_default": True,
            }
            if data.get("label_name"):
                kwargs["label_name"] = data["label_name"]

            obj, created = CleanupRule.objects.get_or_create(
                name=data["name"],
                defaults=kwargs,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  + {obj.name}"))
            else:
                skipped_count += 1
                self.stdout.write(f"  = {obj.name} [already exists]")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created_count} rules created, {skipped_count} already existed.\n"
            "Run dry-run to preview: /admin/gmail/ops/ → Dry-run All Enabled Rules"
        ))
