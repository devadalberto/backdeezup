"""Phase 35 — cleanup undo (untrash) + protect-sender button.
Isolated from tests.py (the large Gmail suite).
"""
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from google_gmail_backup.models import CleanupAuditLog, CleanupRule, GmailMessage, ProtectedSender
from google_gmail_backup.services_rules import protect_sender, undo_audit_log


def _trashed_msg(i):
    return GmailMessage.objects.create(
        gmail_id=f"m{i}", thread_id=f"t{i}", subject=f"s{i}",
        from_address="sender@example.com", date=timezone.now() - timedelta(days=60),
        state=GmailMessage.STATE_TRASHED, account_email="me@test.com",
        deleted_at=timezone.now(), deletion_source="cleanup_rule",
    )


def _audit(action="trash", dry_run=False, ids=None, undone_at=None):
    return CleanupAuditLog.objects.create(
        rule=None, rule_name="Old promos", action=action, dry_run=dry_run,
        actor_label="test", status="OK", affected_count=len(ids or []),
        affected_gmail_ids=ids or [], finished_at=timezone.now(), undone_at=undone_at,
    )


# ── undo_audit_log: refusal cases ────────────────────────────────────────────────

@pytest.mark.django_db
def test_undo_skips_dry_run_audit():
    audit = _audit(dry_run=True, ids=["m1"])
    result = undo_audit_log(audit)
    assert result["skipped"] is True
    assert result["restored"] == 0


@pytest.mark.django_db
def test_undo_skips_already_undone():
    audit = _audit(ids=["m1"], undone_at=timezone.now())
    result = undo_audit_log(audit)
    assert result["skipped"] is True


@pytest.mark.django_db
def test_undo_skips_permanent_delete():
    audit = _audit(action="permanent_delete", ids=["m1"])
    result = undo_audit_log(audit)
    assert result["skipped"] is True
    assert "not restorable" in result["reason"]


@pytest.mark.django_db
def test_undo_skips_non_trash_action():
    audit = _audit(action="star", ids=["m1"])
    result = undo_audit_log(audit)
    assert result["skipped"] is True


@pytest.mark.django_db
def test_undo_raises_when_not_authenticated():
    audit = _audit(ids=["m1"])
    with patch("google_gmail_backup.services_rules.gmail_service", return_value=None):
        with pytest.raises(RuntimeError):
            undo_audit_log(audit)


# ── undo_audit_log: happy path + partial failure ─────────────────────────────────

@pytest.mark.django_db
def test_undo_restores_messages_and_marks_audit_undone():
    m1 = _trashed_msg(1)
    m2 = _trashed_msg(2)
    audit = _audit(ids=[m1.gmail_id, m2.gmail_id])

    with patch("google_gmail_backup.services_rules.gmail_service", return_value=MagicMock()), \
         patch("google_gmail_backup.services_rules.untrash_message", return_value=True) as untrash:
        result = undo_audit_log(audit)

    assert result["restored"] == 2
    assert result["failed"] == []
    assert untrash.call_count == 2

    audit.refresh_from_db()
    assert audit.undone_at is not None

    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.state == GmailMessage.STATE_VERIFIED
    assert m1.deleted_at is None
    assert m1.deletion_source == ""

    undo_log = CleanupAuditLog.objects.get(id=result["undo_audit_id"])
    assert undo_log.action == "untrash"
    assert undo_log.affected_count == 2


@pytest.mark.django_db
def test_undo_partial_failure_reports_per_message_and_only_restores_successes():
    m1 = _trashed_msg(1)
    m2 = _trashed_msg(2)
    audit = _audit(ids=[m1.gmail_id, m2.gmail_id])

    with patch("google_gmail_backup.services_rules.gmail_service", return_value=MagicMock()), \
         patch("google_gmail_backup.services_rules.untrash_message", side_effect=[True, False]):
        result = undo_audit_log(audit)

    assert result["restored"] == 1
    assert result["failed"] == [m2.gmail_id]

    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.state == GmailMessage.STATE_VERIFIED
    assert m2.state == GmailMessage.STATE_TRASHED  # untouched -- untrash failed


@pytest.mark.django_db
def test_undo_twice_is_a_no_op_second_time():
    m1 = _trashed_msg(1)
    audit = _audit(ids=[m1.gmail_id])
    with patch("google_gmail_backup.services_rules.gmail_service", return_value=MagicMock()), \
         patch("google_gmail_backup.services_rules.untrash_message", return_value=True):
        undo_audit_log(audit)
        second = undo_audit_log(audit)
    assert second["skipped"] is True


@pytest.mark.django_db
def test_undo_notes_truncation():
    audit = _audit(ids=["m1"])
    audit.affected_ids_truncated = True
    audit.save()
    with patch("google_gmail_backup.services_rules.gmail_service", return_value=MagicMock()), \
         patch("google_gmail_backup.services_rules.untrash_message", return_value=True):
        result = undo_audit_log(audit)
    assert result["truncated_note"]


# ── protect_sender ────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_protect_sender_creates_row():
    sender = protect_sender("Family@Example.com", label_to_apply="family", star=True)
    assert sender.email == "family@example.com"
    assert ProtectedSender.objects.count() == 1


@pytest.mark.django_db
def test_protect_sender_is_idempotent_and_keeps_existing_settings():
    protect_sender("family@example.com", label_to_apply="family", star=True)
    again = protect_sender("family@example.com", label_to_apply="different", star=False)
    assert ProtectedSender.objects.count() == 1
    assert again.label_to_apply == "family"  # unchanged by the second call
    assert again.star is True


@pytest.mark.django_db
def test_protected_sender_is_excluded_by_apply_rule():
    from google_gmail_backup.services_rules import apply_rule
    rule = CleanupRule.objects.create(
        name="Trash old", gmail_query="", action=CleanupRule.ACTION_TRASH,
        min_age_days=30, enabled=True,
    )
    msg = GmailMessage.objects.create(
        gmail_id="protected1", thread_id="t1", subject="s1",
        from_address="family@example.com", date=timezone.now() - timedelta(days=60),
        state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
    )
    protect_sender("family@example.com")
    audit = apply_rule(rule, dry_run=True)
    assert msg.gmail_id not in audit.affected_gmail_ids
    assert audit.affected_count == 0


# ── API endpoints ─────────────────────────────────────────────────────────────────

@pytest.fixture
def staff_client(client, db, settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "undo-test"}}
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_protect_endpoint_creates_row(staff_client):
    resp = staff_client.post("/api/gmail/protected-senders/protect?email=new@example.com")
    assert resp.status_code == 200
    assert resp.json()["protected"] is True
    assert ProtectedSender.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
def test_undo_endpoint_restores_via_audit_id(staff_client):
    m1 = _trashed_msg(1)
    audit = _audit(ids=[m1.gmail_id])
    with patch("google_gmail_backup.services_rules.gmail_service", return_value=MagicMock()), \
         patch("google_gmail_backup.services_rules.untrash_message", return_value=True):
        resp = staff_client.post(f"/api/gmail/audit-log/{audit.id}/undo")
    assert resp.status_code == 200
    assert resp.json()["restored"] == 1
