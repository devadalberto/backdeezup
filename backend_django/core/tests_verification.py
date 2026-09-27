"""Phase 31 — verification report + integrity check tests."""
import hashlib
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from core import tasks, verification
from google_gmail_backup.models import GmailMessage
from google_media_backup.models import DriveAsset


@pytest.fixture
def staff_client(client, db):
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    client.force_login(user)
    return client


def _drive_asset(i, state, path="", md5=""):
    return DriveAsset.objects.create(
        drive_id=f"d{i}", name=f"f{i}", mime_type="image/jpeg",
        state=state, download_path=path, md5_checksum=md5,
    )


def _gmail_message(i, state, path="", sha=""):
    return GmailMessage.objects.create(
        gmail_id=f"g{i}", account_email="a@b.c",
        state=state, raw_path=path, sha256=sha,
    )


@pytest.mark.django_db
def test_backed_up_states_match_docs():
    assert verification.DRIVE_BACKED_UP_STATES == ("VERIFIED", "DELETE_PENDING", "DELETED")
    assert verification.GMAIL_BACKED_UP_STATES == ("VERIFIED", "TRASHED", "SOFT_DELETED", "DELETED")


@pytest.mark.django_db
def test_build_report_counts_backed_up_and_missing(tmp_path):
    present = tmp_path / "present.bin"
    present.write_bytes(b"data")

    _drive_asset(1, "VERIFIED", path=str(present))
    _drive_asset(2, "DELETE_PENDING", path=str(tmp_path / "gone.bin"))  # missing on disk
    _drive_asset(3, "DISCOVERED")  # not backed up, excluded

    _gmail_message(1, "VERIFIED", path=str(present))
    _gmail_message(2, "TRASHED", path=str(tmp_path / "gone2.bin"))  # missing on disk
    _gmail_message(3, "DOWNLOADED")  # not backed up, excluded

    report = verification.build_report()
    assert report["drive"]["backed_up"] == 2
    assert report["drive"]["missing_on_disk"] == 1
    assert report["gmail"]["backed_up"] == 2
    assert report["gmail"]["missing_on_disk"] == 1
    assert report["total_backed_up"] == 4
    assert report["total_missing_on_disk"] == 2
    assert report["latest_integrity_run"] is None


@pytest.mark.django_db
def test_verification_page_requires_staff(client):
    resp = client.get("/dashboard/verification/")
    assert resp.status_code == 302 and "login" in resp["Location"]


@pytest.mark.django_db
def test_verification_page_renders_real_data(staff_client, tmp_path):
    present = tmp_path / "present.bin"
    present.write_bytes(b"data")
    _drive_asset(1, "VERIFIED", path=str(present))

    resp = staff_client.get("/dashboard/verification/")
    assert resp.status_code == 200
    assert b"VERIFICATION REPORT" in resp.content
    assert b"1" in resp.content  # backed-up total shows up somewhere


@pytest.mark.django_db
def test_task_integrity_check_flags_missing_and_mismatch_without_touching_state(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)  # Phase 42 stale-.part scan walks MEDIA_ROOT
    ok_path = tmp_path / "ok.bin"
    ok_path.write_bytes(b"hello")
    ok_md5 = hashlib.md5(b"hello").hexdigest()

    bad_path = tmp_path / "bad.bin"
    bad_path.write_bytes(b"corrupted")

    _drive_asset(1, "VERIFIED", path=str(ok_path), md5=ok_md5)
    _drive_asset(2, "VERIFIED", path=str(bad_path), md5=ok_md5)  # content changed -> mismatch
    _drive_asset(3, "VERIFIED", path=str(tmp_path / "missing.bin"), md5=ok_md5)  # missing

    result = tasks.task_integrity_check(sample_size=10)

    assert result["sampled"] == 3
    assert result["ok"] == 1
    assert result["missing"] == 1
    assert result["mismatched"] == 1

    # never flips item state
    assert set(DriveAsset.objects.values_list("state", flat=True)) == {"VERIFIED"}


@pytest.mark.django_db
def test_task_integrity_check_creates_integrity_run_row(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    path = tmp_path / "x.bin"
    path.write_bytes(b"content")
    _gmail_message(1, "VERIFIED", path=str(path), sha=hashlib.sha256(b"content").hexdigest())

    tasks.task_integrity_check(sample_size=10)

    from core.models import IntegrityRun
    run = IntegrityRun.objects.latest("started_at")
    assert run.sampled == 1 and run.ok == 1 and run.missing == 0 and run.mismatched == 0
    assert run.finished_at is not None


@pytest.mark.django_db
def test_integrity_check_notifies_only_when_problems_found(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    ok_path = tmp_path / "ok.bin"
    ok_path.write_bytes(b"hello")
    ok_md5 = hashlib.md5(b"hello").hexdigest()
    _drive_asset(1, "VERIFIED", path=str(ok_path), md5=ok_md5)

    with patch("core.notify.send") as send:
        tasks.task_integrity_check(sample_size=10)
    send.assert_not_called()

    _drive_asset(2, "VERIFIED", path=str(tmp_path / "missing.bin"), md5=ok_md5)
    with patch("core.notify.send") as send:
        tasks.task_integrity_check(sample_size=10)
    send.assert_called_once()
    assert send.call_args.args[0] == "integrity_problems_found"
