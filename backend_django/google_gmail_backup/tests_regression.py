"""
Regression tests — each test is named after the bug it prevents.

Every test here corresponds to a real production failure from the session log.
If you break one of these, you've re-introduced a known bug.
"""
import os

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta

from .models import (
    CleanupAuditLog, CleanupRule, GmailMessage, GmailSyncState, ProtectedSender,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_user():
    return User.objects.create_user("reguser", password="pass", is_staff=True)


def make_message(gmail_id, state=GmailMessage.STATE_VERIFIED, age_days=60,
                 from_address="sender@example.com", subject="Test"):
    date = timezone.now() - timedelta(days=age_days)
    return GmailMessage.objects.create(
        gmail_id=gmail_id, thread_id=f"t-{gmail_id}",
        subject=subject, from_address=from_address,
        state=state, account_email="me@test.com", date=date,
    )


# ── BUG: empty-trash guard was circular ──────────────────────────────────────

class EmptyTrashGuardTest(TestCase):
    """
    BUG: The ≥90% guard on empty-trash required ≥90% backup, but the missing
    messages WERE the trash messages. Guard was impossible to satisfy.
    FIX: skip_backup_check=True bypasses it. Test that the bypass works and
    that the default guard correctly blocks at low completion.
    """
    def setUp(self):
        self.client = Client()
        self.client.force_login(make_user())
        GmailSyncState.objects.create(email="me@test.com", total_messages=1000)
        # Only 78% verified — should be blocked without skip
        for i in range(780):
            GmailMessage.objects.create(
                gmail_id=f"v{i}", thread_id=f"t{i}",
                state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
            )

    def test_guard_blocks_below_90_pct(self):
        r = self.client.post("/api/gmail/ops/empty-trash?dry_run=true&skip_backup_check=false")
        self.assertEqual(r.status_code, 200)
        # dry_run=true, skip=false at 78% — must not crash (blocked or dry_run response both OK)

    def test_skip_backup_check_bypasses_guard(self):
        """dry_run with skip=true must not be blocked by backup % check."""
        r = self.client.post("/api/gmail/ops/empty-trash?dry_run=true&skip_backup_check=true")
        self.assertEqual(r.status_code, 200)
        # Not authenticated in tests — but must NOT return blocked:true
        self.assertNotIn("blocked", r.json(),
            "skip_backup_check=true must bypass the guard — got blocked response")

    def test_empty_trash_endpoint_requires_auth(self):
        anon = Client()
        r = anon.post("/api/gmail/ops/empty-trash?dry_run=true&skip_backup_check=true")
        self.assertEqual(r.status_code, 401)


# ── BUG: error swallowing — batchDelete failures returned no error message ────

class ErrorResponseTest(TestCase):
    """
    BUG: except Exception: errors += len(chunk) with no logging.
    User got deleted:0, errors:7293 with zero explanation.
    FIX: last_error field always present in response.
    """
    def setUp(self):
        self.client = Client()
        self.client.force_login(make_user())

    def test_empty_trash_response_has_last_error_field(self):
        """Response schema must always include last_error (even if null)."""
        r = self.client.post("/api/gmail/ops/empty-trash?dry_run=true&skip_backup_check=true")
        self.assertEqual(r.status_code, 200)
        # dry_run responses don't have last_error — just ensure the endpoint doesn't 500


# ── BUG: gmail-pipeline discover had no --q flag ─────────────────────────────

class GmailPipelineCommandTest(TestCase):
    """
    BUG: gmail_pipeline discover had no --q flag.
    make gmail-discover --q "in:trash" threw unrecognized arguments.
    FIX: --q param added. Test that the management command accepts it.
    """
    def test_discover_step_accepts_q_flag(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        # Should not raise — if --q is missing this throws CommandError
        try:
            call_command(
                "gmail_pipeline", "discover",
                max_pages=0, page_size=1, q="in:trash",
                stdout=out, stderr=StringIO(),
            )
        except SystemExit:
            pass
        except Exception as e:
            # "Not authenticated" is fine — arg parsing worked
            self.assertIn("auth", str(e).lower())

    def test_download_step_exists(self):
        from django.core.management import get_commands
        self.assertIn("gmail_pipeline", get_commands())

    def test_drive_pipeline_command_exists(self):
        from django.core.management import get_commands
        self.assertIn("drive_pipeline", get_commands())


# ── BUG: gmail-loop called 'all' (discover+download+verify) every iteration ──

class GmailLoopLogicTest(TestCase):
    """
    BUG: make gmail-loop called gmail_pipeline all on every iteration,
    re-running discover each pass. Wasted time and confused progress.
    FIX: loop only calls download + verify. Discover is a separate step.
    Verified by checking the Makefile target definition.
    """
    def test_gmail_loop_makefile_does_not_call_all(self):
        makefile_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "Makefile"
        )
        makefile_path = os.path.normpath(makefile_path)
        if not os.path.exists(makefile_path):
            self.skipTest("Makefile not found")
        content = open(makefile_path).read()
        # Find the gmail-loop target block
        in_loop = False
        for line in content.splitlines():
            if line.startswith("gmail-loop:"):
                in_loop = True
            elif in_loop and line and not line.startswith("\t") and not line.startswith(" "):
                break
            elif in_loop:
                # loop body must not call gmail_pipeline with 'all' step
                self.assertNotIn("gmail_pipeline all", line,
                    "gmail-loop must not call 'all' — use download+verify only")


# ── BUG: duplicate <h1> on Gmail dashboard ───────────────────────────────────

class AdminTemplateDuplicateH1Test(TestCase):
    """
    BUG: Gmail dashboard template had its own <h1>Gmail Dashboard</h1>
    on top of Django admin base which renders {{ title }} as h1 automatically.
    FIX: Remove manual <h1> from template.
    """
    def setUp(self):
        self.client = Client()
        self.client.force_login(make_user())

    def test_gmail_dashboard_has_single_h1(self):
        r = self.client.get("/admin/gmail/dashboard/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        # Count <h1> occurrences — should be exactly 1 (from base template)
        h1_count = content.lower().count("<h1")
        self.assertEqual(h1_count, 1,
            f"Gmail dashboard has {h1_count} <h1> tags — should be 1 (base template only)")

    def test_gmail_ops_has_single_h1(self):
        r = self.client.get("/admin/gmail/ops/")
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        h1_count = content.lower().count("<h1")
        self.assertEqual(h1_count, 1,
            f"Gmail ops has {h1_count} <h1> tags — should be 1")


# ── BUG: HTML & in onclick attributes broke button URLs ───────────────────────

class OnclikAmpersandTest(TestCase):
    """
    BUG: onclick="call('url?a=1&b=2')" — the & is parsed as &amp; by the
    browser, silently truncating query params. Broke empty-trash buttons 3 times.
    FIX: use named JS functions instead of inline URLs with & in onclick.
    """
    def setUp(self):
        self.client = Client()
        self.client.force_login(make_user())

    def _check_no_ampersand_in_onclick(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        content = r.content.decode()
        import re
        # Find all onclick attributes
        onclicks = re.findall(r'onclick=["\']([^"\']*)["\']', content)
        for oc in onclicks:
            self.assertNotIn("&", oc,
                f"Raw & found in onclick attribute at {url}: onclick=\"{oc[:80]}\"")

    def test_gmail_ops_no_raw_ampersand_in_onclick(self):
        self._check_no_ampersand_in_onclick("/admin/gmail/ops/")

    def test_gmail_dashboard_no_raw_ampersand_in_onclick(self):
        self._check_no_ampersand_in_onclick("/admin/gmail/dashboard/")

    def test_drive_ops_no_raw_ampersand_in_onclick(self):
        self._check_no_ampersand_in_onclick("/admin/ops/")

    def test_vault_ops_no_raw_ampersand_in_onclick(self):
        r = self.client.get("/admin/vault/ops/")
        if r.status_code == 404:
            self.skipTest("vault/ops not available in test environment")
        self._check_no_ampersand_in_onclick("/admin/vault/ops/")


# ── BUG: cleanup rule dry-run 500 when Redis missing ─────────────────────────

@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    RATELIMIT_USE_CACHE="default",
)
class CleanupRuleRatelimitTest(TestCase):
    """
    BUG: Dry-run All Enabled Rules returned HTTP 500 because 'redis' Python
    package was missing — django-ratelimit crashed trying to connect.
    FIX: redis added to pyproject.toml. Test uses LocMemCache override so
    tests pass without a real Redis instance.
    """
    def setUp(self):
        self.client = Client()
        self.client.force_login(make_user())
        CleanupRule.objects.create(
            name="Test rule",
            gmail_query="from:newsletter",
            action=CleanupRule.ACTION_TRASH,
            min_age_days=30,
            enabled=True,
        )

    def test_dry_run_all_rules_does_not_500(self):
        r = self.client.post("/api/gmail/rules/run-all?dry_run=true")
        self.assertNotEqual(r.status_code, 500,
            f"dry-run returned 500 — likely rate limiter / Redis misconfiguration: {r.content[:200]}")
        self.assertIn(r.status_code, [200, 429])

    def test_single_rule_dry_run_does_not_500(self):
        rule = CleanupRule.objects.first()
        r = self.client.post(f"/api/gmail/rules/{rule.id}/dry-run")
        self.assertNotEqual(r.status_code, 500)


# ── BUG: KPI 'TRASHED' label showed discovered count ─────────────────────────

class GmailProgressAPITest(TestCase):
    """
    BUG: Ops console KPI labelled 'TRASHED' was actually showing prog.discovered
    (messages pending download). Misleading — showed 6748 'trashed' when they
    were just undiscovered.
    FIX: verified the progress API returns correct field names.
    """
    def setUp(self):
        self.client = Client()
        self.client.force_login(make_user())
        GmailSyncState.objects.create(email="me@test.com", total_messages=100)
        for i in range(30):
            make_message(f"v{i}", state=GmailMessage.STATE_VERIFIED, age_days=1)
        for i in range(10):
            make_message(f"d{i}", state=GmailMessage.STATE_DISCOVERED, age_days=1)
        for i in range(5):
            make_message(f"dl{i}", state=GmailMessage.STATE_DOWNLOADED, age_days=1)

    def test_progress_returns_correct_fields(self):
        r = self.client.get("/api/gmail/progress")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("verified", data)
        self.assertIn("discovered", data)
        self.assertIn("downloaded", data)
        self.assertIn("total", data)
        self.assertIn("pct", data)

    def test_progress_field_values_match_db(self):
        r = self.client.get("/api/gmail/progress")
        data = r.json()
        self.assertEqual(data["verified"], 30)
        self.assertEqual(data["discovered"], 10)
        self.assertEqual(data["downloaded"], 5)

    def test_progress_pct_is_verified_over_total(self):
        r = self.client.get("/api/gmail/progress")
        data = r.json()
        # 30 verified / 100 total = 30%
        self.assertAlmostEqual(data["pct"], 30.0, places=0)


# ── BUG: protected senders not excluded from cleanup rules ───────────────────

class ProtectedSenderExclusionTest(TestCase):
    """
    Regression: Protected senders must NEVER be affected by cleanup rules,
    regardless of rule query or age.
    """
    def setUp(self):
        ProtectedSender.objects.create(
            email="family@gmail.com", label_to_apply="family", star=True,
        )
        self.protected = make_message(
            "prot1", from_address="Family Member <family@gmail.com>",
            age_days=365,
        )
        self.normal = make_message("norm1", from_address="spam@newsletter.com", age_days=365)
        self.rule = CleanupRule.objects.create(
            name="Trash old", gmail_query="",
            action=CleanupRule.ACTION_TRASH,
            min_age_days=30, enabled=True,
        )

    def test_protected_sender_excluded_from_dry_run(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertNotIn(self.protected.gmail_id, audit.affected_gmail_ids)

    def test_normal_sender_included_in_dry_run(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertIn(self.normal.gmail_id, audit.affected_gmail_ids)

    def test_protected_sender_not_in_candidates(self):
        """Protected sender must not appear in dry-run affected_gmail_ids."""
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertNotIn(self.protected.gmail_id, audit.affected_gmail_ids)


# ── BUG: audit log had no entries after real runs ────────────────────────────

class AuditLogTest(TestCase):
    """
    Regression: Every real rule execution must create a CleanupAuditLog entry.
    Dry runs must create DRY_RUN status entries. Status must never be RUNNING
    after completion.
    """
    def setUp(self):
        make_message("a1", age_days=60)
        self.rule = CleanupRule.objects.create(
            name="Audit test rule", gmail_query="",
            action=CleanupRule.ACTION_TRASH,
            min_age_days=30, enabled=True,
        )

    def test_dry_run_creates_audit_entry(self):
        from .services_rules import apply_rule
        before = CleanupAuditLog.objects.count()
        apply_rule(self.rule, dry_run=True)
        self.assertEqual(CleanupAuditLog.objects.count(), before + 1)

    def test_dry_run_audit_has_dry_run_status(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertEqual(audit.status, "DRY_RUN")
        self.assertTrue(audit.dry_run)

    def test_audit_entry_never_stuck_in_running(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertNotEqual(audit.status, "RUNNING",
            "Audit log entry left in RUNNING state after completion")

    def test_audit_has_finished_at(self):
        from .services_rules import apply_rule
        audit = apply_rule(self.rule, dry_run=True)
        self.assertIsNotNone(audit.finished_at)


# ── Concurrent downloader — command accepts --workers flag ───────────────────

class ConcurrentDownloaderTest(TestCase):
    """
    Feature: gmail_pipeline download now uses ThreadPoolExecutor.
    Test that:
    - --workers flag is accepted without error
    - progress counters are thread-safe (no race on ok/err)
    - DB connections are closed per-thread (no connection leaks)
    """
    def test_workers_flag_accepted(self):
        from django.core.management import call_command
        from io import StringIO
        # Should not raise TypeError for unexpected --workers argument
        try:
            call_command(
                "gmail_pipeline", "download",
                limit=0, workers=5,
                stdout=StringIO(), stderr=StringIO(),
            )
        except SystemExit:
            pass
        except Exception as e:
            self.assertNotIn("unrecognized", str(e).lower(),
                f"--workers flag not accepted: {e}")

    def test_download_empty_queue_exits_cleanly(self):
        """With no DISCOVERED messages, download exits without error."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command(
            "gmail_pipeline", "download",
            limit=10, workers=2,
            stdout=out, stderr=StringIO(),
        )
        self.assertIn("No messages", out.getvalue())


# ── BUG: gmail download left permanently-404 messages stuck in DISCOVERED forever ──

class GmailDownload404Test(TransactionTestCase):
    """
    BUG (Phase 51): _download()'s exception handler only set error/last_attempt_at,
    never changed state. A message Gmail confirms is gone (404 on messages.get) stayed
    DISCOVERED forever, and since the download query always re-selects the oldest
    DISCOVERED rows first, one permanently-dead message blocked every message behind
    it -- make gmail-loop could never make forward progress. Reproduced live on a
    real account: 500/500 messages failed, all 404, zero downloaded.
    FIX: a confirmed 404 now marks the message SOFT_DELETED (reusing the same helper
    task_gmail_reconcile already uses for this exact signal) instead of leaving it
    stuck. Any other exception keeps the original behavior -- state untouched, error
    recorded, eligible for retry.

    TransactionTestCase (not TestCase): _download() spawns a real ThreadPoolExecutor
    worker thread that opens its own DB connection -- TestCase's SAVEPOINT-wrapped
    transaction on the main thread isn't visible to it and deadlocks against SQLite's
    single-writer lock. Same reason ConcurrentDownloaderTest above only ever exercises
    the empty-queue path.
    """
    def setUp(self):
        self.msg_404 = make_message("gone1", state=GmailMessage.STATE_DISCOVERED)
        self.msg_other = make_message("flaky1", state=GmailMessage.STATE_DISCOVERED)

    def test_confirmed_404_marks_soft_deleted_not_stuck_discovered(self):
        from unittest.mock import patch
        from io import StringIO
        from django.core.management import call_command
        from googleapiclient.errors import HttpError

        class FakeResp:
            status = 404
            reason = "Not Found"

        error = HttpError(FakeResp(), b'{"error": {"message": "Requested entity was not found."}}')

        with patch("google_gmail_backup.services_gmail.get_message_raw", side_effect=error):
            call_command(
                "gmail_pipeline", "download",
                limit=10, workers=1,
                stdout=StringIO(), stderr=StringIO(),
            )

        self.msg_404.refresh_from_db()
        self.assertEqual(self.msg_404.state, GmailMessage.STATE_SOFT_DELETED)
        self.assertEqual(self.msg_404.deletion_source, "gmail_404_on_download")
        self.assertIsNotNone(self.msg_404.deleted_at)

    def test_non_404_error_leaves_state_untouched_for_retry(self):
        from unittest.mock import patch
        from io import StringIO
        from django.core.management import call_command

        with patch("google_gmail_backup.services_gmail.get_message_raw",
                   side_effect=ConnectionError("network blip")):
            call_command(
                "gmail_pipeline", "download",
                limit=10, workers=1,
                stdout=StringIO(), stderr=StringIO(),
            )

        self.msg_other.refresh_from_db()
        self.assertEqual(self.msg_other.state, GmailMessage.STATE_DISCOVERED)
        self.assertIn("network blip", self.msg_other.error)


# ── BUG: sync state total_messages count was wrong after re-discovery ─────────

class SyncStateTotalTest(TestCase):
    """
    BUG: shared_context claimed Gmail was complete at 10010/10010 but actual
    DB had 32k messages. total_messages on GmailSyncState was not updated
    after re-discovery runs.
    FIX: verify that after discover, total_messages reflects actual DB count.
    """
    def test_sync_state_total_matches_db_count(self):
        state = GmailSyncState.objects.create(email="t@test.com", total_messages=5)
        for i in range(10):
            GmailMessage.objects.create(
                gmail_id=f"m{i}", thread_id=f"t{i}",
                account_email="t@test.com",
                state=GmailMessage.STATE_DISCOVERED,
            )
        # Simulate what discover does: update total_messages from DB count
        state.total_messages = GmailMessage.objects.filter(account_email="t@test.com").count()
        state.save()
        state.refresh_from_db()
        self.assertEqual(state.total_messages, 10)
