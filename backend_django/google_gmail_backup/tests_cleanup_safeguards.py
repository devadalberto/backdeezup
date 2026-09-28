"""Phase 34 — cleanup safeguards: dry-run-required confirm, global pause,
never-delete-with-attachments. Isolated from tests.py (the large Gmail suite).
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from google_gmail_backup.models import CleanupRule, GmailMessage, RuleCondition
from google_gmail_backup.services_rules import (
    apply_rule,
    dry_run_confirmation_error,
    is_cleanup_paused,
    run_all_enabled_rules,
)


@pytest.fixture
def rule(db):
    return CleanupRule.objects.create(
        name="Old promos", gmail_query="", action=CleanupRule.ACTION_TRASH,
        min_age_days=30, enabled=True,
    )


def _msg(i, has_attachments=False, age_days=60):
    return GmailMessage.objects.create(
        gmail_id=f"m{i}", thread_id=f"t{i}", subject=f"s{i}",
        from_address="sender@example.com", date=timezone.now() - timedelta(days=age_days),
        state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        has_attachments=has_attachments,
    )


# ── dry_run_confirmation_error (Execute UI gate) ───────────────────────────────

@pytest.mark.django_db
def test_confirmation_error_when_no_dry_run_yet(rule):
    assert dry_run_confirmation_error(rule, 5) is not None


@pytest.mark.django_db
def test_confirmation_error_when_dry_run_stale(rule):
    rule.last_dry_run_at = timezone.now() - timedelta(hours=25)
    rule.last_dry_run_count = 3
    rule.save()
    assert dry_run_confirmation_error(rule, 3) is not None


@pytest.mark.django_db
def test_confirmation_error_when_count_mismatch(rule):
    rule.last_dry_run_at = timezone.now()
    rule.last_dry_run_count = 5
    rule.save()
    assert dry_run_confirmation_error(rule, 4) is not None


@pytest.mark.django_db
def test_confirmation_ok_when_fresh_and_matching(rule):
    rule.last_dry_run_at = timezone.now()
    rule.last_dry_run_count = 5
    rule.save()
    assert dry_run_confirmation_error(rule, 5) is None


@pytest.mark.django_db
def test_confirmation_disabled_via_setting(rule, settings):
    settings.CLEANUP_REQUIRE_DRY_RUN = False
    assert dry_run_confirmation_error(rule, None) is None


@pytest.mark.django_db
def test_apply_rule_dry_run_sets_last_dry_run_at(rule):
    _msg(1)
    audit = apply_rule(rule, dry_run=True)
    rule.refresh_from_db()
    assert audit.status == "DRY_RUN"
    assert rule.last_dry_run_at is not None
    assert rule.last_dry_run_count == 1


# ── Global pause ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_is_cleanup_paused_reads_setting(settings):
    settings.CLEANUP_PAUSED = False
    assert is_cleanup_paused() is False
    settings.CLEANUP_PAUSED = True
    assert is_cleanup_paused() is True


@pytest.mark.django_db
def test_paused_apply_rule_noops_without_touching_gmail(rule, settings):
    settings.CLEANUP_PAUSED = True
    with patch("google_gmail_backup.services_rules.gmail_service", side_effect=AssertionError("must not be called")):
        audit = apply_rule(rule, dry_run=False, actor_label="test")
    assert audit.status == "PAUSED"
    assert audit.affected_count == 0


@pytest.mark.django_db
def test_paused_run_all_enabled_rules_returns_empty(rule, settings):
    settings.CLEANUP_PAUSED = True
    assert run_all_enabled_rules(dry_run=False, actor_label="test") == []


@pytest.mark.django_db
def test_unpaused_dry_run_is_unaffected_by_pause(rule, settings):
    settings.CLEANUP_PAUSED = True
    _msg(1)
    audit = apply_rule(rule, dry_run=True)
    assert audit.status == "DRY_RUN"


# ── never_delete_with_attachments ────────────────────────────────────────────────

@pytest.mark.django_db
def test_never_delete_with_attachments_excludes_from_dry_run(rule):
    rule.never_delete_with_attachments = True
    rule.save()
    with_attach = _msg(1, has_attachments=True)
    without_attach = _msg(2, has_attachments=False)

    audit = apply_rule(rule, dry_run=True)

    assert audit.affected_count == 1
    assert without_attach.gmail_id in audit.affected_gmail_ids
    assert with_attach.gmail_id not in audit.affected_gmail_ids


@pytest.mark.django_db
def test_never_delete_with_attachments_syncs_rule_condition(rule):
    rule.never_delete_with_attachments = True
    rule.save()
    apply_rule(rule, dry_run=True)
    assert rule.conditions.filter(
        field=RuleCondition.FIELD_HAS_ATTACH, operator=RuleCondition.OP_NOT_EQUALS,
    ).exists()

    rule.never_delete_with_attachments = False
    rule.save()
    apply_rule(rule, dry_run=True)
    assert not rule.conditions.filter(
        field=RuleCondition.FIELD_HAS_ATTACH, operator=RuleCondition.OP_NOT_EQUALS,
    ).exists()


# ── Phase 69: dry-run must apply rule conditions, not just age ───────────────────

@pytest.mark.django_db
def test_dry_run_applies_gmail_query_not_just_age():
    """Before Phase 69, dry-run counted state+age only and ignored
    rule.gmail_query entirely — Execute (which DOES apply gmail_query
    against live Gmail) could affect a completely different set than what
    the dry-run preview showed. Two messages are equally old; only one
    matches the rule's gmail_query per the mocked live search — dry-run
    must report exactly that one, not both."""
    rule = CleanupRule.objects.create(
        name="Newsletter cleanup", gmail_query="from:newsletter",
        action=CleanupRule.ACTION_TRASH, min_age_days=30, enabled=True,
    )
    matching = _msg(1)
    matching.gmail_id = "matches-query"
    matching.save()
    non_matching = _msg(2)
    non_matching.gmail_id = "does-not-match-query"
    non_matching.save()

    mock_svc = MagicMock()
    mock_svc.users.return_value.messages.return_value.list.return_value.execute.return_value = {
        "messages": [{"id": "matches-query"}],
    }
    with patch("google_gmail_backup.services_rules.gmail_service", return_value=mock_svc) as mocked:
        audit = apply_rule(rule, dry_run=True)

    assert mocked.called, "dry-run must call gmail_service() when rule.gmail_query is set"
    assert audit.affected_count == 1
    assert audit.affected_gmail_ids == ["matches-query"]


@pytest.mark.django_db
def test_dry_run_skips_gmail_query_call_when_query_is_empty(rule):
    """rule fixture has gmail_query="" — dry-run must NOT call gmail_service
    at all in that case (no behavior change for age-only rules)."""
    _msg(1)
    with patch("google_gmail_backup.services_rules.gmail_service", side_effect=AssertionError("must not be called")):
        audit = apply_rule(rule, dry_run=True)
    assert audit.affected_count == 1


# ── /api/gmail/rules/{id}/execute — new Execute UI gate ──────────────────────────

@pytest.fixture
def staff_client(client, db, settings):
    # @ratelimit on rule_execute needs a reachable cache backend; the real Redis
    # in config/settings.py isn't reachable in this test environment.
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "cleanup-test"}}
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_execute_endpoint_refuses_without_dry_run(staff_client, rule):
    resp = staff_client.post(f"/api/gmail/rules/{rule.id}/execute")
    assert resp.status_code == 400
    assert "error" in resp.json()


@pytest.mark.django_db
def test_execute_endpoint_refuses_on_count_mismatch(staff_client, rule):
    rule.last_dry_run_at = timezone.now()
    rule.last_dry_run_count = 7
    rule.save()
    resp = staff_client.post(f"/api/gmail/rules/{rule.id}/execute?confirm_count=6")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_execute_endpoint_succeeds_with_fresh_matching_dry_run(staff_client, rule):
    rule.last_dry_run_at = timezone.now()
    rule.last_dry_run_count = 0
    rule.save()
    with patch("google_gmail_backup.services_rules.gmail_service", return_value=MagicMock(
        users=lambda: MagicMock(messages=lambda: MagicMock(
            list=lambda **k: MagicMock(execute=lambda: {"messages": []}),
        )),
    )):
        resp = staff_client.post(f"/api/gmail/rules/{rule.id}/execute?confirm_count=0")
    assert resp.status_code == 200
    assert resp.json()["affected"] == 0
