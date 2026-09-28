"""Phase 70 — analyze_mail_patterns: header-signal mining into SuggestedRule."""
from email.message import EmailMessage
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from google_gmail_backup.models import CleanupRule, GmailMessage, RuleCondition, SuggestedRule


def _write_eml(tmp_path, name, headers: dict, body: str = "hello") -> str:
    msg = EmailMessage()
    for key, value in headers.items():
        msg[key] = value
    msg.set_content(body)
    path = tmp_path / f"{name}.eml"
    path.write_bytes(bytes(msg))
    return str(path)


def _msg(tmp_path, i, from_address, headers, age_days=10):
    return GmailMessage.objects.create(
        gmail_id=f"m{i}", thread_id=f"t{i}", subject=f"subject {i}",
        from_address=from_address,
        from_email_normalized=from_address.lower(),
        date=timezone.now() - timezone.timedelta(days=age_days),
        state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        raw_path=_write_eml(tmp_path, f"m{i}", headers),
    )


def _run():
    out = StringIO()
    call_command("analyze_mail_patterns", stdout=out)
    return out.getvalue()


@pytest.mark.django_db
def test_list_unsubscribe_creates_suggestion(tmp_path):
    _msg(tmp_path, 1, "deals@retailer.example",
         {"List-Unsubscribe": "<mailto:unsub@retailer.example>"})

    _run()

    s = SuggestedRule.objects.get(sender_domain="retailer.example",
                                   signal_type=SuggestedRule.SignalType.LIST_UNSUBSCRIBE)
    assert s.message_count == 1
    assert s.sample_sender == "deals@retailer.example"


@pytest.mark.django_db
def test_precedence_bulk_detected(tmp_path):
    _msg(tmp_path, 1, "list@forum.example", {"Precedence": "bulk"})
    _run()
    assert SuggestedRule.objects.filter(
        sender_domain="forum.example", signal_type=SuggestedRule.SignalType.PRECEDENCE_BULK,
    ).exists()


@pytest.mark.django_db
def test_reply_to_mismatch_detected(tmp_path):
    _msg(tmp_path, 1, "noreply@sender.example", {"Reply-To": "care@othercompany.example"})
    _run()
    assert SuggestedRule.objects.filter(
        sender_domain="sender.example", signal_type=SuggestedRule.SignalType.REPLY_TO_MISMATCH,
    ).exists()


@pytest.mark.django_db
def test_plain_message_with_no_signals_creates_nothing(tmp_path):
    _msg(tmp_path, 1, "friend@example.com", {})
    _run()
    assert SuggestedRule.objects.count() == 0


@pytest.mark.django_db
def test_domain_already_covered_by_enabled_rule_is_skipped(tmp_path):
    rule = CleanupRule.objects.create(
        name="Existing", gmail_query="from:retailer.example",
        action=CleanupRule.ACTION_TRASH, min_age_days=30, enabled=True,
    )
    RuleCondition.objects.create(
        rule=rule, order=1, field=RuleCondition.FIELD_SENDER,
        operator=RuleCondition.OP_CONTAINS, value="retailer.example",
    )
    _msg(tmp_path, 1, "deals@retailer.example",
         {"List-Unsubscribe": "<mailto:unsub@retailer.example>"})

    _run()

    assert SuggestedRule.objects.count() == 0


@pytest.mark.django_db
def test_rerun_is_idempotent_and_updates_count(tmp_path):
    _msg(tmp_path, 1, "deals@retailer.example",
         {"List-Unsubscribe": "<mailto:unsub@retailer.example>"})
    _run()
    _msg(tmp_path, 2, "deals@retailer.example",
         {"List-Unsubscribe": "<mailto:unsub@retailer.example>"})
    _run()

    qs = SuggestedRule.objects.filter(sender_domain="retailer.example",
                                       signal_type=SuggestedRule.SignalType.LIST_UNSUBSCRIBE)
    assert qs.count() == 1
    assert qs.first().message_count == 2


@pytest.mark.django_db
def test_dismissed_suggestion_is_not_resurfaced(tmp_path):
    _msg(tmp_path, 1, "deals@retailer.example",
         {"List-Unsubscribe": "<mailto:unsub@retailer.example>"})
    _run()
    s = SuggestedRule.objects.get(sender_domain="retailer.example")
    s.dismissed = True
    s.message_count = 1
    s.save()

    _msg(tmp_path, 2, "deals@retailer.example",
         {"List-Unsubscribe": "<mailto:unsub@retailer.example>"})
    _run()

    s.refresh_from_db()
    assert s.dismissed is True
    assert s.message_count == 1  # untouched, not bumped to 2


@pytest.mark.django_db
def test_missing_eml_file_is_skipped_gracefully():
    GmailMessage.objects.create(
        gmail_id="ghost", thread_id="t", subject="s",
        from_address="x@example.com", from_email_normalized="x@example.com",
        date=timezone.now() - timezone.timedelta(days=10),
        state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        raw_path="/nonexistent/path/does-not-exist.eml",
    )
    output = _run()
    assert "1 missing .eml file skipped" in output
    assert SuggestedRule.objects.count() == 0


@pytest.mark.django_db
def test_admin_create_draft_rule_action_builds_disabled_rule():
    from django.contrib.admin.sites import AdminSite

    from google_gmail_backup.admin import SuggestedRuleAdmin

    suggestion = SuggestedRule.objects.create(
        sender_domain="retailer.example",
        signal_type=SuggestedRule.SignalType.LIST_UNSUBSCRIBE,
        message_count=42, sample_sender="deals@retailer.example",
        sample_subjects=["50% off!"],
    )
    admin_instance = SuggestedRuleAdmin(SuggestedRule, AdminSite())
    admin_instance.message_user = lambda *a, **k: None  # skip messages-framework plumbing

    class _Req:
        pass

    admin_instance.create_draft_rule(_Req(), SuggestedRule.objects.filter(pk=suggestion.pk))

    suggestion.refresh_from_db()
    assert suggestion.created_rule is not None
    assert suggestion.dismissed is True
    rule = suggestion.created_rule
    assert rule.enabled is False
    assert rule.dry_run_default is True
    assert "retailer.example" in rule.gmail_query
    assert rule.conditions.filter(field=RuleCondition.FIELD_SENDER, value="retailer.example").exists()
