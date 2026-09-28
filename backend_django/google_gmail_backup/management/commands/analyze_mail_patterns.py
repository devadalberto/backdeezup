"""
Phase 70: scan already-downloaded mail for header-level bulk-mail signals
(List-Unsubscribe, List-Id, Precedence: bulk, From/Reply-To and From/Return-Path
domain mismatches) that Gmail's own category classifier doesn't expose as a rule
condition, and surface them as SuggestedRule rows for human review.

Read-only by construction: parses headers from .eml files already on disk
(GmailMessage.raw_path) -- no Gmail API calls. Never creates or enables a
CleanupRule; a human reviews suggestions in the admin and accepts them there.

Usage:
    make analyze-mail-patterns
    make analyze-mail-patterns ARGS="--limit 5000"
"""
from email import message_from_bytes
from email.utils import parseaddr

from django.core.management.base import BaseCommand

from google_gmail_backup.models import GmailMessage, RuleCondition, SuggestedRule

SAMPLE_SUBJECTS_PER_SUGGESTION = 5


def _domain(email_address: str) -> str:
    addr = parseaddr(email_address or "")[1]
    return addr.split("@")[-1].lower() if "@" in addr else ""


def _signals_for(msg_bytes: bytes, from_address: str) -> set[str]:
    """Return the set of SuggestedRule.SignalType values this message's headers trigger."""
    msg = message_from_bytes(msg_bytes)
    signals = set()

    if msg.get("List-Unsubscribe"):
        signals.add(SuggestedRule.SignalType.LIST_UNSUBSCRIBE)
    if msg.get("List-Id"):
        signals.add(SuggestedRule.SignalType.LIST_ID)

    precedence = (msg.get("Precedence") or "").strip().lower()
    if precedence in ("bulk", "list"):
        signals.add(SuggestedRule.SignalType.PRECEDENCE_BULK)

    from_domain = _domain(from_address)
    reply_to = msg.get("Reply-To")
    if reply_to and from_domain and _domain(reply_to) not in ("", from_domain):
        signals.add(SuggestedRule.SignalType.REPLY_TO_MISMATCH)

    return_path = msg.get("Return-Path")
    if return_path and from_domain and _domain(return_path) not in ("", from_domain):
        signals.add(SuggestedRule.SignalType.RETURN_PATH_MISMATCH)

    return signals


class Command(BaseCommand):
    help = "Read-only: scan downloaded mail for bulk-mail header signals, surface SuggestedRule rows"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20000,
                             help="Max messages to scan (default 20000)")

    def handle(self, *args, **options):
        limit = options["limit"]

        # Domains already covered by an enabled rule's sender condition -- computed
        # once, locally, from structured RuleCondition data (not by re-parsing/
        # re-executing gmail_query strings, and no Gmail API call needed).
        covered_domains = set()
        for value in RuleCondition.objects.filter(
            rule__enabled=True, field=RuleCondition.FIELD_SENDER,
        ).values_list("value", flat=True):
            d = _domain(value) or value.strip().lower().lstrip("@")
            if d:
                covered_domains.add(d)

        qs = (
            GmailMessage.objects
            .filter(state=GmailMessage.STATE_VERIFIED)
            .exclude(raw_path="")
            .order_by("-date")[:limit]
        )

        # (sender_domain, signal_type) -> {"count": int, "sender": str, "subjects": [...]}
        clusters: dict[tuple[str, str], dict] = {}
        scanned = 0
        skipped_missing_file = 0
        skipped_covered = 0

        for msg in qs.iterator():
            domain = _domain(msg.from_address)
            if not domain:
                continue
            if domain in covered_domains:
                skipped_covered += 1
                continue

            try:
                with open(msg.raw_path, "rb") as f:
                    raw = f.read()
            except (FileNotFoundError, OSError):
                skipped_missing_file += 1
                continue

            scanned += 1
            for signal in _signals_for(raw, msg.from_address):
                key = (domain, signal)
                bucket = clusters.setdefault(key, {"count": 0, "sender": msg.from_address, "subjects": []})
                bucket["count"] += 1
                if len(bucket["subjects"]) < SAMPLE_SUBJECTS_PER_SUGGESTION:
                    bucket["subjects"].append(msg.subject[:120])

        created, updated, skipped_dismissed = 0, 0, 0
        for (domain, signal), bucket in clusters.items():
            existing = SuggestedRule.objects.filter(sender_domain=domain, signal_type=signal).first()
            if existing and existing.dismissed:
                skipped_dismissed += 1
                continue
            _, was_created = SuggestedRule.objects.update_or_create(
                sender_domain=domain, signal_type=signal,
                defaults={
                    "message_count": bucket["count"],
                    "sample_sender": bucket["sender"],
                    "sample_subjects": bucket["subjects"],
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(
            f"Scanned {scanned} messages ({skipped_missing_file} missing .eml file skipped, "
            f"{skipped_covered} already covered by an enabled rule skipped).\n"
            f"Suggestions: {created} new, {updated} updated, {skipped_dismissed} previously "
            f"dismissed left untouched.\n"
            f"Review at /admin/google_gmail_backup/suggestedrule/"
        )
