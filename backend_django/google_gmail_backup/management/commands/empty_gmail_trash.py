"""
Permanently delete all messages currently in Gmail trash.

WARNING: This is irreversible. Messages are permanently deleted from Gmail.
Your local .eml backups in media/gmail/ are the only copy after this.

Safety checks:
- Verifies Gmail backup is >= 90% complete before allowing execution
- Requires explicit --confirm flag
- Shows count before executing
- Logs all deletions to CleanupAuditLog
- Uses batchDelete in chunks of 1000 (Gmail API limit)

Usage:
    make gmail-empty-trash-dry      # show how many messages are in trash
    make gmail-empty-trash          # permanently delete all trash
"""
import logging

from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)
BATCH_SIZE = 1000


class Command(BaseCommand):
    help = "Permanently delete all messages in Gmail trash (irreversible — requires confirmed backup)"

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", default=False,
                            help="Required to actually execute deletion")
        parser.add_argument("--skip-backup-check", action="store_true", default=False,
                            help="Skip the backup completeness check (use with caution)")

    def handle(self, *args, **options):
        from google_gmail_backup.models import CleanupAuditLog, GmailMessage, GmailSyncState
        from google_gmail_backup.services_gmail import gmail_service
        from django.utils import timezone
        from django.db.models import Sum

        confirmed = options["confirm"]
        skip_check = options["skip_backup_check"]

        svc = gmail_service()
        if not svc:
            self.stdout.write(self.style.ERROR("Not authenticated. Run: make auth"))
            return

        # ── Safety check: verify backup is sufficiently complete ──────────────
        if not skip_check:
            sync_total = GmailSyncState.objects.aggregate(t=Sum("total_messages"))["t"] or 0
            verified = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count()
            pct = round(verified / max(sync_total, 1) * 100, 1)

            if pct < 90:
                self.stdout.write(self.style.ERROR(
                    f"BLOCKED: Gmail backup is only {pct}% complete ({verified}/{sync_total}).\n"
                    "Run 'make pipeline-gmail' until >= 90% before emptying trash.\n"
                    "Use --skip-backup-check to override (dangerous)."
                ))
                return

            self.stdout.write(self.style.SUCCESS(
                f"Backup check passed: {verified}/{sync_total} messages backed up ({pct}%)"
            ))

        # ── Count messages currently in Gmail trash ───────────────────────────
        self.stdout.write("Counting messages in Gmail trash...")
        trash_ids = []
        page_token = None

        while True:
            params = dict(userId="me", q="in:trash", maxResults=500)
            if page_token:
                params["pageToken"] = page_token
            res = svc.users().messages().list(**params).execute()
            trash_ids.extend([m["id"] for m in res.get("messages", [])])
            page_token = res.get("nextPageToken")
            if not page_token:
                break

        count = len(trash_ids)
        self.stdout.write(self.style.WARNING(f"\nMessages in Gmail trash: {count}"))

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Gmail trash is already empty."))
            return

        if not confirmed:
            self.stdout.write(
                f"\nThis will PERMANENTLY DELETE {count} messages from Gmail.\n"
                "There is NO recovery after this — your .eml backups are the only copy.\n\n"
                "To proceed: make gmail-empty-trash"
            )
            return

        # ── Execute batchDelete in chunks of 1000 ────────────────────────────
        audit = CleanupAuditLog.objects.create(
            rule=None,
            rule_name="Empty Gmail Trash",
            action="permanent_delete",
            dry_run=False,
            actor_label="management_command",
            status="RUNNING",
        )

        deleted = 0
        errors = 0

        from tqdm import tqdm
        chunks = [trash_ids[i:i + BATCH_SIZE] for i in range(0, len(trash_ids), BATCH_SIZE)]

        with tqdm(chunks, desc="deleting", unit="batch",
                  bar_format="{desc}: {percentage:3.0f}% |{bar}| {n_fmt}/{total_fmt} batches [{elapsed}<{remaining}] deleted={postfix[d]}",
                  postfix={"d": 0},
                  file=self.stderr, dynamic_ncols=True) as pbar:
            for chunk in pbar:
                try:
                    svc.users().messages().batchDelete(
                        userId="me",
                        body={"ids": chunk},
                    ).execute()
                    deleted += len(chunk)
                    pbar.postfix["d"] = deleted
                    pbar.set_postfix(pbar.postfix)
                except Exception as exc:
                    log.error("batchDelete chunk failed: %s", exc)
                    errors += len(chunk)

        audit.affected_count = deleted
        audit.affected_gmail_ids = trash_ids[:100]
        audit.affected_ids_truncated = len(trash_ids) > 100
        audit.status = "OK" if errors == 0 else "ERROR"
        audit.error_text = f"{errors} messages failed" if errors else ""
        audit.finished_at = timezone.now()
        audit.save()

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Permanently deleted {deleted} messages from Gmail trash."
            + (f" ({errors} errors)" if errors else "")
        ))
