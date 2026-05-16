from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.utils import timezone

from .models import GmailMessage, GmailAttachment, GmailSyncState


class GmailSyncStateTest(TestCase):
    def test_create_sync_state(self):
        state = GmailSyncState.objects.create(email="test@example.com")
        self.assertEqual(str(state), "test@example.com")
        self.assertIsNone(state.last_history_id)
        self.assertEqual(state.total_messages, 0)

    def test_unique_email(self):
        GmailSyncState.objects.create(email="user@example.com")
        with self.assertRaises(Exception):
            GmailSyncState.objects.create(email="user@example.com")


class GmailMessageModelTest(TestCase):
    def setUp(self):
        self.msg = GmailMessage.objects.create(
            gmail_id="msg001",
            thread_id="thread001",
            subject="Hello World",
            from_address="sender@example.com",
            to_address="me@example.com",
            snippet="Hello...",
            labels=["INBOX"],
            size_estimate=1024,
            account_email="me@example.com",
        )

    def test_default_state_is_discovered(self):
        self.assertEqual(self.msg.state, GmailMessage.STATE_DISCOVERED)

    def test_str_representation(self):
        self.assertIn("Hello World", str(self.msg))

    def test_state_transitions(self):
        self.msg.state = GmailMessage.STATE_DOWNLOADED
        self.msg.downloaded_at = timezone.now()
        self.msg.save()
        self.assertEqual(
            GmailMessage.objects.get(gmail_id="msg001").state,
            GmailMessage.STATE_DOWNLOADED,
        )

    def test_unique_gmail_id(self):
        with self.assertRaises(Exception):
            GmailMessage.objects.create(
                gmail_id="msg001",
                thread_id="thread002",
                account_email="me@example.com",
            )


class GmailAttachmentTest(TestCase):
    def setUp(self):
        self.msg = GmailMessage.objects.create(
            gmail_id="msg002",
            thread_id="thread002",
            account_email="me@example.com",
        )

    def test_create_attachment(self):
        att = GmailAttachment.objects.create(
            message=self.msg,
            attachment_id="att001",
            filename="document.pdf",
            mime_type="application/pdf",
            size=50000,
        )
        self.assertEqual(att.filename, "document.pdf")
        self.assertEqual(att.message.gmail_id, "msg002")

    def test_unique_attachment_per_message(self):
        GmailAttachment.objects.create(
            message=self.msg, attachment_id="att001", filename="a.pdf"
        )
        with self.assertRaises(Exception):
            GmailAttachment.objects.create(
                message=self.msg, attachment_id="att001", filename="b.pdf"
            )


class GmailAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        user = User.objects.create_user("testuser", password="testpass")
        self.client.force_login(user)
        GmailMessage.objects.create(
            gmail_id="g1",
            thread_id="t1",
            subject="Test email",
            from_address="sender@gmail.com",
            state=GmailMessage.STATE_DISCOVERED,
            account_email="me@gmail.com",
        )
        GmailMessage.objects.create(
            gmail_id="g2",
            thread_id="t2",
            subject="Another email",
            from_address="other@gmail.com",
            state=GmailMessage.STATE_DOWNLOADED,
            account_email="me@gmail.com",
        )

    def test_list_messages_all(self):
        r = self.client.get("/api/gmail/messages")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    def test_list_messages_filter_state(self):
        r = self.client.get("/api/gmail/messages?state=DOWNLOADED")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["state"], "DOWNLOADED")

    def test_list_messages_filter_q(self):
        r = self.client.get("/api/gmail/messages?q=Test")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["gmail_id"], "g1")

    def test_gmail_swagger_loads(self):
        r = self.client.get("/api/gmail/docs")
        self.assertEqual(r.status_code, 200)

    def test_gmail_api_requires_auth(self):
        """API endpoints must return 401 for unauthenticated requests."""
        anon_client = Client()
        r = anon_client.get("/api/gmail/profile")
        self.assertEqual(r.status_code, 401)

    def test_trash_dry_run(self):
        r = self.client.post(
            "/api/gmail/cleanup/trash?dry_run=true",
            data='["g1","g2"]',
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["dry_run"])
        self.assertEqual(data["would_trash"], 2)


class CleanupRulesEngineTest(TestCase):
    """Tests for services_rules.py — the core cleanup engine."""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta
        from .models import CleanupRule, ProtectedSender

        # Create old verified messages
        self.old_date = timezone.now() - timedelta(days=60)
        self.recent_date = timezone.now() - timedelta(days=5)

        self.msg_old = GmailMessage.objects.create(
            gmail_id="old1", thread_id="t1", subject="Old newsletter",
            from_address="news@example.com", date=self.old_date,
            state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        )
        self.msg_recent = GmailMessage.objects.create(
            gmail_id="recent1", thread_id="t2", subject="Recent newsletter",
            from_address="news@example.com", date=self.recent_date,
            state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        )
        self.msg_protected = GmailMessage.objects.create(
            gmail_id="protected1", thread_id="t3", subject="Family email",
            from_address="family@gmail.com", date=self.old_date,
            state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        )
        self.protected_sender = ProtectedSender.objects.create(
            email="family@gmail.com", label_to_apply="family", star=True,
        )
        self.rule = CleanupRule.objects.create(
            name="Test trash old",
            gmail_query="",
            action=CleanupRule.ACTION_TRASH,
            min_age_days=30,
            enabled=True,
            dry_run_default=True,
        )

    def test_dry_run_counts_candidates(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertEqual(audit.status, "DRY_RUN")
        # Only old message qualifies (recent one is < 30 days)
        # Protected sender excluded
        self.assertEqual(audit.affected_count, 1)
        self.assertIn(self.msg_old.gmail_id, audit.affected_gmail_ids)

    def test_dry_run_excludes_recent_messages(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertNotIn(self.msg_recent.gmail_id, audit.affected_gmail_ids)

    def test_dry_run_excludes_protected_senders(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertNotIn(self.msg_protected.gmail_id, audit.affected_gmail_ids)

    def test_dry_run_does_not_change_state(self):
        from .services_rules import apply_rule
        apply_rule(self.rule, dry_run=True)
        # Messages should remain VERIFIED after dry run
        self.msg_old.refresh_from_db()
        self.assertEqual(self.msg_old.state, GmailMessage.STATE_VERIFIED)

    def test_audit_log_truncation_flag(self):
        from .services_rules import apply_rule
        from .models import CleanupAuditLog
        audit = apply_rule(self.rule, dry_run=True)
        # With only 1 candidate, should not be truncated
        self.assertFalse(audit.affected_ids_truncated)

    def test_normalize_email_extracts_from_angle_brackets(self):
        from .services_rules import _normalize_email
        self.assertEqual(_normalize_email("Name <email@test.com>"), "email@test.com")
        self.assertEqual(_normalize_email("plain@test.com"), "plain@test.com")
        self.assertEqual(_normalize_email("  UPPER@TEST.COM  "), "upper@test.com")

    def test_rule_min_age_days_cutoff(self):
        """Rule with min_age_days=7 should include recent message but exclude nothing old."""
        from .services_rules import apply_rule
        self.rule.min_age_days = 3
        self.rule.save()
        audit = apply_rule(self.rule, dry_run=True)
        # Both old and recent should qualify (both > 3 days old)
        self.assertEqual(audit.affected_count, 2)
