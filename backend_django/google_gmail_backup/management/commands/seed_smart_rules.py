"""
Seed v2 smart cleanup rules for LinkedIn, job boards, recruiters,
and marketing platforms using compound RuleCondition logic.

Safe to run multiple times (skips existing rules by name).

Usage:
    make seed-smart-rules
"""
from django.core.management.base import BaseCommand


SMART_RULES = [
    # ── LinkedIn ──────────────────────────────────────────────────────────────
    {
        "name": "LinkedIn — Job-related (label work/jobs)",
        "description": "Emails from LinkedIn that are about actual jobs — label for review",
        "action": "label",
        "label_name": "work/jobs",
        "min_age_days": 0,
        "enabled": False,
        "conditions": [
            {"field": "sender",  "operator": "contains",     "value": "linkedin.com",  "logic": "AND", "order": 1},
            {"field": "subject", "operator": "contains",     "value": "job",           "logic": "OR",  "order": 2},
            {"field": "subject", "operator": "contains",     "value": "recruiter",     "logic": "OR",  "order": 3},
            {"field": "subject", "operator": "contains",     "value": "applied",       "logic": "OR",  "order": 4},
            {"field": "subject", "operator": "contains",     "value": "hiring",        "logic": "OR",  "order": 5},
            {"field": "subject", "operator": "contains",     "value": "interview",     "logic": "OR",  "order": 6},
            {"field": "subject", "operator": "contains",     "value": "offer",         "logic": "AND", "order": 7},
        ],
    },
    {
        "name": "LinkedIn — Non-job notifications (trash after 30d)",
        "description": "LinkedIn notifications that are not job-related",
        "action": "trash",
        "label_name": "",
        "min_age_days": 30,
        "enabled": False,
        "conditions": [
            {"field": "sender",  "operator": "contains",     "value": "linkedin.com",  "logic": "AND", "order": 1},
            {"field": "subject", "operator": "not_contains", "value": "job",           "logic": "AND", "order": 2},
            {"field": "subject", "operator": "not_contains", "value": "recruiter",     "logic": "AND", "order": 3},
            {"field": "subject", "operator": "not_contains", "value": "applied",       "logic": "AND", "order": 4},
            {"field": "subject", "operator": "not_contains", "value": "interview",     "logic": "AND", "order": 5},
            {"field": "subject", "operator": "not_contains", "value": "offer",         "logic": "AND", "order": 6},
        ],
    },
    # ── Job boards ────────────────────────────────────────────────────────────
    {
        "name": "Job boards — alerts (label work/jobs)",
        "description": "Job alerts from Monster, Indeed, Glassdoor, ZipRecruiter, Dice",
        "action": "label",
        "label_name": "work/jobs",
        "min_age_days": 0,
        "enabled": False,
        "conditions": [
            {"field": "sender", "operator": "contains", "value": "monster.com",      "logic": "OR", "order": 1},
            {"field": "sender", "operator": "contains", "value": "indeed.com",       "logic": "OR", "order": 2},
            {"field": "sender", "operator": "contains", "value": "glassdoor.com",    "logic": "OR", "order": 3},
            {"field": "sender", "operator": "contains", "value": "ziprecruiter.com", "logic": "OR", "order": 4},
            {"field": "sender", "operator": "contains", "value": "dice.com",         "logic": "AND", "order": 5},
        ],
    },
    # ── Recruiter outreach ────────────────────────────────────────────────────
    {
        "name": "Recruiter outreach (label work/recruiters)",
        "description": "Direct recruiter emails based on subject keywords",
        "action": "label",
        "label_name": "work/recruiters",
        "min_age_days": 0,
        "enabled": False,
        "conditions": [
            {"field": "subject", "operator": "contains", "value": "opportunity",       "logic": "OR", "order": 1},
            {"field": "subject", "operator": "contains", "value": "your background",   "logic": "OR", "order": 2},
            {"field": "subject", "operator": "contains", "value": "your profile",      "logic": "OR", "order": 3},
            {"field": "subject", "operator": "contains", "value": "I came across",     "logic": "OR", "order": 4},
            {"field": "subject", "operator": "contains", "value": "exciting role",     "logic": "OR", "order": 5},
            {"field": "subject", "operator": "contains", "value": "perfect fit",       "logic": "AND", "order": 6},
        ],
    },
    # ── Marketing platforms ───────────────────────────────────────────────────
    {
        "name": "Marketing platforms (trash after 30d)",
        "description": "Emails from Mailchimp, HubSpot, Salesforce, Constant Contact, Marketo",
        "action": "trash",
        "label_name": "",
        "min_age_days": 30,
        "enabled": False,
        "conditions": [
            {"field": "sender", "operator": "contains", "value": "mailchimp.com",       "logic": "OR", "order": 1},
            {"field": "sender", "operator": "contains", "value": "hubspot.com",         "logic": "OR", "order": 2},
            {"field": "sender", "operator": "contains", "value": "salesforce.com",      "logic": "OR", "order": 3},
            {"field": "sender", "operator": "contains", "value": "constantcontact.com", "logic": "OR", "order": 4},
            {"field": "sender", "operator": "contains", "value": "marketo.com",         "logic": "OR", "order": 5},
            {"field": "sender", "operator": "contains", "value": "klaviyo.com",         "logic": "OR", "order": 6},
            {"field": "sender", "operator": "contains", "value": "sendgrid.net",        "logic": "AND", "order": 7},
        ],
    },
    # ── E-commerce / retail ───────────────────────────────────────────────────
    {
        "name": "E-commerce order confirmations (archive)",
        "description": "Archive order/shipping confirmations after 90 days",
        "action": "archive",
        "label_name": "",
        "min_age_days": 90,
        "enabled": False,
        "conditions": [
            {"field": "subject", "operator": "contains", "value": "order confirmation", "logic": "OR",  "order": 1},
            {"field": "subject", "operator": "contains", "value": "has shipped",        "logic": "OR",  "order": 2},
            {"field": "subject", "operator": "contains", "value": "your receipt",       "logic": "OR",  "order": 3},
            {"field": "subject", "operator": "contains", "value": "order #",            "logic": "AND", "order": 4},
        ],
    },
    # ── App notifications ─────────────────────────────────────────────────────
    {
        "name": "App notification emails (trash after 60d)",
        "description": "Automated notifications from apps and services",
        "action": "trash",
        "label_name": "",
        "min_age_days": 60,
        "enabled": False,
        "conditions": [
            {"field": "sender", "operator": "contains",     "value": "notifications@", "logic": "OR",  "order": 1},
            {"field": "sender", "operator": "contains",     "value": "alerts@",        "logic": "OR",  "order": 2},
            {"field": "sender", "operator": "contains",     "value": "noreply@",       "logic": "AND", "order": 3},
            {"field": "subject", "operator": "not_contains","value": "invoice",        "logic": "AND", "order": 4},
            {"field": "subject", "operator": "not_contains","value": "receipt",        "logic": "AND", "order": 5},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed v2 smart cleanup rules with compound RuleCondition logic (idempotent)"

    def handle(self, *args, **options):
        from google_gmail_backup.models import CleanupRule, RuleCondition
        from google_gmail_backup.query_compiler import compile_conditions

        created = skipped = 0

        for rule_data in SMART_RULES:
            if CleanupRule.objects.filter(name=rule_data["name"]).exists():
                self.stdout.write(f"  EXISTS  {rule_data['name']}")
                skipped += 1
                continue

            rule = CleanupRule.objects.create(
                name=rule_data["name"],
                description=rule_data["description"],
                action=rule_data["action"],
                label_name=rule_data.get("label_name", ""),
                min_age_days=rule_data["min_age_days"],
                enabled=rule_data["enabled"],
                dry_run_default=True,
                gmail_query="",  # will be compiled below
            )

            conditions = []
            for cdata in rule_data["conditions"]:
                c = RuleCondition.objects.create(
                    rule=rule,
                    order=cdata["order"],
                    field=cdata["field"],
                    operator=cdata["operator"],
                    value=cdata["value"],
                    logic=cdata["logic"],
                )
                conditions.append(c)

            compiled = compile_conditions(conditions)
            rule.gmail_query = compiled
            rule.save(update_fields=["gmail_query"])

            self.stdout.write(self.style.SUCCESS(
                f"  CREATED {rule.name}\n          query: {compiled[:80]}"
            ))
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created} smart rules created, {skipped} already existed.\n"
            "All rules are DISABLED by default.\n"
            "1. Review in /admin/google_gmail_backup/cleanuprule/\n"
            "2. Run dry-runs from /admin/gmail/ops/ or make cleanup-dry\n"
            "3. Enable rules you trust, then make cleanup-run"
        ))
