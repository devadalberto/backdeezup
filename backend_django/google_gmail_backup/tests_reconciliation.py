"""
Tests for Phase 2 — Gmail sync & reconciliation.

Covers:
- Incremental sync: TRASH label added/removed transitions
- Reconciliation: 404 and TRASH detection
- Purge: expired SOFT_DELETED records transition to DELETED
- Rules engine: metadata_snapshot population after trash
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from .models import CleanupRule, GmailMessage, GmailSyncState, ProtectedSender


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_message(
    gmail_id,
    state=GmailMessage.STATE_VERIFIED,
    age_days=10,
    from_address="sender@example.com",
    subject="Test Subject",
    deleted_at=None,
    deletion_source="",
):
    """Create a GmailMessage with sensible defaults for reconciliation tests."""
    date = timezone.now() - timedelta(days=age_days)
    return GmailMessage.objects.create(
        gmail_id=gmail_id,
        thread_id=f"t-{gmail_id}",
        subject=subject,
        from_address=from_address,
        to_address="me@test.com",
        date=date,
        labels=["INBOX"],
        size_estimate=2048,
        state=state,
        account_email="me@test.com",
        deleted_at=deleted_at,
        deletion_source=deletion_source,
    )


def make_sync_state(history_id="12345"):
    """Create a GmailSyncState with a valid history ID."""
    return GmailSyncState.objects.create(
        email="me@test.com",
        last_history_id=history_id,
    )


# ── Incremental Sync Tests ───────────────────────────────────────────────────


class IncrementalSyncTrashAddedTest(TestCase):
    """TRASH label added via history -> message transitions to SOFT_DELETED."""

    def setUp(self):
        self.msg = make_message("msg_trash_add")
        self.sync_state = make_sync_state()

    @patch("google_gmail_backup.services_gmail.get_authenticated_email")
    @patch("google_gmail_backup.services_gmail.list_history")
    def test_trash_label_added_sets_soft_deleted(self, mock_history, mock_email):
        from .tasks import task_gmail_incremental_sync

        mock_email.return_value = "me@test.com"
        mock_history.return_value = (
            [
                {
                    "labelsAdded": [
                        {
                            "message": {"id": "msg_trash_add"},
                            "labelIds": ["TRASH"],
                        }
                    ]
                }
            ],
            "99999",
        )

        task_gmail_incremental_sync()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_SOFT_DELETED)
        self.assertIsNotNone(self.msg.deleted_at)
        self.assertEqual(self.msg.deletion_source, "gmail_user")
        self.assertTrue(self.msg.metadata_snapshot)
        self.assertEqual(self.msg.metadata_snapshot["subject"], "Test Subject")
        self.assertEqual(self.msg.metadata_snapshot["from_address"], "sender@example.com")


class IncrementalSyncTrashRemovedTest(TestCase):
    """TRASH label removed via history -> message reverts to VERIFIED."""

    def setUp(self):
        self.msg = make_message(
            "msg_trash_remove",
            state=GmailMessage.STATE_SOFT_DELETED,
            deleted_at=timezone.now() - timedelta(days=2),
            deletion_source="gmail_user",
        )
        self.sync_state = make_sync_state()

    @patch("google_gmail_backup.services_gmail.get_authenticated_email")
    @patch("google_gmail_backup.services_gmail.list_history")
    def test_trash_label_removed_reverts_to_verified(self, mock_history, mock_email):
        from .tasks import task_gmail_incremental_sync

        mock_email.return_value = "me@test.com"
        mock_history.return_value = (
            [
                {
                    "labelsRemoved": [
                        {
                            "message": {"id": "msg_trash_remove"},
                            "labelIds": ["TRASH"],
                        }
                    ]
                }
            ],
            "99999",
        )

        task_gmail_incremental_sync()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_VERIFIED)
        self.assertIsNone(self.msg.deleted_at)
        self.assertEqual(self.msg.deletion_source, "")


# ── Reconciliation Tests ─────────────────────────────────────────────────────


class Reconcile404Test(TestCase):
    """Message returns 404 from Gmail -> SOFT_DELETED with deletion_source=gmail_sync."""

    def setUp(self):
        self.msg = make_message("msg_404")

    @patch("google_gmail_backup.services_gmail.gmail_service")
    def test_404_marks_soft_deleted(self, mock_gmail_svc):
        from .tasks import task_gmail_reconcile

        svc = MagicMock()
        mock_gmail_svc.return_value = svc
        svc.users().messages().list.return_value.execute.return_value = {
            "messages": [], "nextPageToken": None,
        }

        # messages().get() raises an exception containing "404"
        error = Exception("HttpError 404: Message not found")
        svc.users().messages().get.return_value.execute.side_effect = error

        task_gmail_reconcile()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_SOFT_DELETED)
        self.assertIsNotNone(self.msg.deleted_at)
        self.assertEqual(self.msg.deletion_source, "gmail_sync")
        self.assertTrue(self.msg.metadata_snapshot)
        self.assertEqual(self.msg.metadata_snapshot["subject"], "Test Subject")


class ReconcileTrashLabelTest(TestCase):
    """Message has TRASH in labelIds -> SOFT_DELETED with deletion_source=gmail_user."""

    def setUp(self):
        self.msg = make_message("msg_in_trash")

    @patch("google_gmail_backup.services_gmail.gmail_service")
    def test_trash_label_present_marks_soft_deleted(self, mock_gmail_svc):
        from .tasks import task_gmail_reconcile

        svc = MagicMock()
        mock_gmail_svc.return_value = svc
        svc.users().messages().list.return_value.execute.return_value = {
            "messages": [], "nextPageToken": None,
        }

        svc.users().messages().get.return_value.execute.return_value = {
            "id": "msg_in_trash",
            "labelIds": ["TRASH", "IMPORTANT"],
        }

        task_gmail_reconcile()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_SOFT_DELETED)
        self.assertIsNotNone(self.msg.deleted_at)
        self.assertEqual(self.msg.deletion_source, "gmail_user")
        self.assertTrue(self.msg.metadata_snapshot)


class ReconcileMessageAliveTest(TestCase):
    """Message still alive in Gmail -> stays VERIFIED, no changes."""

    def setUp(self):
        self.msg = make_message("msg_alive")

    @patch("google_gmail_backup.services_gmail.gmail_service")
    def test_alive_message_stays_verified(self, mock_gmail_svc):
        from .tasks import task_gmail_reconcile

        svc = MagicMock()
        mock_gmail_svc.return_value = svc
        svc.users().messages().list.return_value.execute.return_value = {
            "messages": [], "nextPageToken": None,
        }

        svc.users().messages().get.return_value.execute.return_value = {
            "id": "msg_alive",
            "labelIds": ["INBOX"],
        }

        task_gmail_reconcile()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_VERIFIED)
        self.assertIsNone(self.msg.deleted_at)
        self.assertEqual(self.msg.deletion_source, "")


# ── Purge Tests ──────────────────────────────────────────────────────────────


class PurgeExpiredTest(TestCase):
    """SOFT_DELETED records older than 90 days transition to DELETED."""

    def setUp(self):
        self.msg = make_message(
            "msg_expired",
            state=GmailMessage.STATE_SOFT_DELETED,
            deleted_at=timezone.now() - timedelta(days=91),
            deletion_source="gmail_user",
        )

    def test_expired_record_purged_to_deleted(self):
        from .tasks import task_purge_expired_soft_deletes

        result = task_purge_expired_soft_deletes()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_DELETED)
        self.assertTrue(self.msg.metadata_snapshot)
        self.assertEqual(self.msg.metadata_snapshot["subject"], "Test Subject")
        self.assertEqual(result["purged"], 1)


class PurgeYoungRecordUntouchedTest(TestCase):
    """SOFT_DELETED records younger than 90 days are not purged."""

    def setUp(self):
        self.msg = make_message(
            "msg_young",
            state=GmailMessage.STATE_SOFT_DELETED,
            deleted_at=timezone.now() - timedelta(days=30),
            deletion_source="gmail_user",
        )

    def test_young_record_stays_soft_deleted(self):
        from .tasks import task_purge_expired_soft_deletes

        result = task_purge_expired_soft_deletes()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_SOFT_DELETED)
        self.assertEqual(result["purged"], 0)


# ── Rules Engine Metadata Snapshot Test ──────────────────────────────────────


class RulesEngineMetadataSnapshotTest(TestCase):
    """apply_rule with trash action populates metadata_snapshot on affected messages."""

    def setUp(self):
        self.msg = make_message("msg_rule_trash", age_days=60)
        self.rule = CleanupRule.objects.create(
            name="Test trash for snapshot",
            gmail_query="",
            action=CleanupRule.ACTION_TRASH,
            min_age_days=30,
            enabled=True,
            dry_run_default=True,
        )

    @patch("google_gmail_backup.services_rules.gmail_service")
    @patch("google_gmail_backup.services_rules.trash_message")
    def test_metadata_snapshot_populated_after_trash(self, mock_trash, mock_svc):
        from .services_rules import apply_rule

        mock_trash.return_value = True
        svc = MagicMock()
        mock_svc.return_value = svc

        audit = apply_rule(self.rule, dry_run=False)

        self.msg.refresh_from_db()
        self.assertTrue(self.msg.metadata_snapshot)
        self.assertEqual(self.msg.metadata_snapshot["subject"], "Test Subject")
        self.assertEqual(self.msg.metadata_snapshot["from_address"], "sender@example.com")
        self.assertEqual(self.msg.metadata_snapshot["to_address"], "me@test.com")
        self.assertIn("date", self.msg.metadata_snapshot)
        self.assertEqual(self.msg.metadata_snapshot["labels"], ["INBOX"])
        self.assertEqual(self.msg.metadata_snapshot["size_estimate"], 2048)
        self.assertEqual(audit.status, "OK")


# ── Protected Sender Reconciliation Test ─────────────────────────────────────


class ProtectedSenderReconcileTest(TestCase):
    """
    Reconciliation operates on message state, not sender identity.
    A protected sender's message that returns 404 still gets marked SOFT_DELETED
    because reconciliation reflects Gmail reality, not cleanup policy.
    """

    def setUp(self):
        ProtectedSender.objects.create(
            email="family@gmail.com", label_to_apply="family", star=True,
        )
        self.msg = make_message(
            "msg_protected_404",
            from_address="family@gmail.com",
        )

    @patch("google_gmail_backup.services_gmail.gmail_service")
    def test_protected_sender_still_soft_deleted_on_404(self, mock_gmail_svc):
        from .tasks import task_gmail_reconcile

        svc = MagicMock()
        mock_gmail_svc.return_value = svc
        svc.users().messages().list.return_value.execute.return_value = {
            "messages": [], "nextPageToken": None,
        }

        error = Exception("HttpError 404: notFound")
        svc.users().messages().get.return_value.execute.side_effect = error

        task_gmail_reconcile()

        self.msg.refresh_from_db()
        self.assertEqual(self.msg.state, GmailMessage.STATE_SOFT_DELETED)
        self.assertEqual(self.msg.deletion_source, "gmail_sync")
