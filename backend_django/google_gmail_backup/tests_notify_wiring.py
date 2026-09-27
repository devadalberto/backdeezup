"""Phase 33 — notification wiring on Gmail task failures. Isolated from the
main test.py / regression suites: this only exercises the notify call sites,
not the Gmail API mocking those files carry.
"""
from unittest.mock import patch

import pytest

from google_gmail_backup.services_rules import _notify_cleanup_executed
from google_gmail_backup.tasks import _record_task_failure


@pytest.mark.django_db
def test_generic_failure_notifies_backup_task_failure():
    with patch("core.notify.send") as send:
        _record_task_failure("some_task", Exception("boom"))
    send.assert_called_once()
    assert send.call_args.args[0] == "backup_task_failure"


@pytest.mark.django_db
def test_invalid_grant_also_notifies_oauth_revoked():
    with patch("core.notify.send") as send:
        _record_task_failure("some_task", Exception("invalid_grant: Token has been expired or revoked."))
    events = {c.args[0] for c in send.call_args_list}
    assert events == {"oauth_revoked", "backup_task_failure"}


@pytest.mark.django_db
def test_record_task_failure_never_raises_when_notify_is_broken():
    with patch("core.notify.send", side_effect=Exception("network is down")):
        _record_task_failure("some_task", Exception("boom"))  # must not raise


def test_cleanup_executed_helper_fires_notify():
    with patch("core.notify.send") as send:
        _notify_cleanup_executed("Old promos", "trash", 42)
    send.assert_called_once_with(
        "cleanup_executed",
        "Cleanup rule 'Old promos' executed",
        "Action 'trash' affected 42 message(s).",
    )


def test_cleanup_executed_helper_never_raises_when_notify_is_broken():
    with patch("core.notify.send", side_effect=Exception("network is down")):
        _notify_cleanup_executed("Old promos", "trash", 42)  # must not raise
