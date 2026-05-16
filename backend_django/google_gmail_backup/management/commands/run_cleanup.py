"""
Management command to run cleanup rules with safety checks.

Usage:
    make cleanup-dry          # dry-run all enabled rules (safe)
    make cleanup-run          # execute all enabled rules (REAL)
    make cleanup-run ARGS="--rule 1"   # run specific rule by ID

Safety:
- Dry-run by default
- Shows affected counts before executing
- Requires --confirm flag to actually execute
- All actions logged to CleanupAuditLog
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run cleanup rules with safety checks and audit logging"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=True,
                            help="Dry-run only (default)")
        parser.add_argument("--execute", action="store_true", default=False,
                            help="Actually execute rules (requires --confirm)")
        parser.add_argument("--confirm", action="store_true", default=False,
                            help="Required confirmation for --execute")
        parser.add_argument("--rule", type=int, default=None,
                            help="Run only this rule ID (default: all enabled)")

    def handle(self, *args, **options):
        from google_gmail_backup.models import CleanupRule
        from google_gmail_backup.services_rules import apply_rule

        execute = options["execute"]
        confirmed = options["confirm"]
        rule_id = options["rule"]
        dry_run = not execute

        if execute and not confirmed:
            self.stdout.write(self.style.ERROR(
                "ERROR: --execute requires --confirm. "
                "Review the dry-run output first, then add --confirm."
            ))
            return

        if rule_id:
            qs = CleanupRule.objects.filter(id=rule_id)
            if not qs.exists():
                self.stdout.write(self.style.ERROR(f"Rule {rule_id} not found."))
                return
        else:
            qs = CleanupRule.objects.filter(enabled=True).order_by("name")
            if not qs.exists():
                self.stdout.write(self.style.WARNING(
                    "No enabled cleanup rules found. "
                    "Enable rules in /admin/google_gmail_backup/cleanuprule/ first."
                ))
                return

        from tqdm import tqdm

        mode = "DRY RUN" if dry_run else "EXECUTE"
        rules_list = list(qs)
        self.stdout.write(f"\nCleanup Rules — {mode} ({len(rules_list)} rules)\n")

        total_affected = 0
        with tqdm(
            rules_list,
            desc="rules",
            unit="rule",
            bar_format=(
                "{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt} "
                "[{elapsed}<{remaining}, {rate_fmt}] msgs={postfix[msgs]}"
            ),
            postfix={"msgs": 0},
            file=self.stderr,
            dynamic_ncols=True,
        ) as pbar:
            for rule in pbar:
                pbar.set_description(rule.name[:40])
                try:
                    audit = apply_rule(rule, dry_run=dry_run, actor_label="management_command")
                    status = "DRY" if dry_run else "DONE"
                    self.stdout.write(
                        f"  [{status}] {rule.name} — {audit.affected_count} messages"
                    )
                    if audit.sample_subjects and dry_run:
                        for s in audit.sample_subjects[:3]:
                            self.stdout.write(f"    • {s[:60]}")
                    total_affected += audit.affected_count
                    pbar.postfix["msgs"] = total_affected
                    pbar.set_postfix(pbar.postfix)
                except Exception as exc:
                    self.stdout.write(f"  ERROR {rule.name}: {exc}")

        action_word = "would affect" if dry_run else "affected"
        self.stdout.write(f"\nTotal {action_word}: {total_affected} messages")
        if dry_run:
            self.stdout.write("To execute: make cleanup-run")
