"""Phase 37 — restore to local dir + conflict handling + restore smoke test.
No Google network calls: everything here is real local files (tmp_path) + real DB rows.
"""
import os

import pytest
from django.utils import timezone

from core.export import resolve_export_items
from core.models import IntegrityRun
from core.restore import resolve_dest_root, restore_items, sha256_file
from google_gmail_backup.models import GmailMessage
from google_media_backup.models import DriveAsset


def _gmail_msg(tmp_path, i, content=b"hello eml", date=None):
    p = tmp_path / f"msg{i}.eml"
    p.write_bytes(content)
    return GmailMessage.objects.create(
        gmail_id=f"g{i}", thread_id=f"t{i}", subject=f"s{i}",
        from_address="a@example.com", date=date or timezone.now(),
        state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        raw_path=str(p),
    )


def _drive_asset(tmp_path, i, content=b"hello drive file"):
    p = tmp_path / f"asset{i}.bin"
    p.write_bytes(content)
    return DriveAsset.objects.create(
        drive_id=f"d{i}", name=f"file{i}.bin", mime_type="application/octet-stream",
        size_bytes=len(content), state=DriveAsset.State.VERIFIED, download_path=str(p),
    )


# ── path traversal guard ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_resolve_dest_root_rejects_traversal(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    with pytest.raises(ValueError):
        resolve_dest_root("../../etc")


@pytest.mark.django_db
def test_resolve_dest_root_accepts_plain_subdir(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    dest = resolve_dest_root("job1")
    assert dest == str((tmp_path / "restores" / "job1").resolve())
    assert os.path.isdir(dest)


# ── basic restore ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_restore_copies_file_and_preserves_content(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    m = _gmail_msg(tmp_path, 1, content=b"payload one")
    items = resolve_export_items("selection", gmail_ids=[m.pk])

    results = restore_items(items, dest_subdir="job1")
    assert results[0]["action"] == "copied"
    assert open(results[0]["dest_path"], "rb").read() == b"payload one"


@pytest.mark.django_db
def test_restore_preserves_gmail_date_as_mtime(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    fixed_date = timezone.now().replace(microsecond=0) - timezone.timedelta(days=400)
    m = _gmail_msg(tmp_path, 1, date=fixed_date)
    items = resolve_export_items("selection", gmail_ids=[m.pk])

    results = restore_items(items, dest_subdir="job1")
    restored_mtime = int(os.path.getmtime(results[0]["dest_path"]))
    assert restored_mtime == int(fixed_date.timestamp())


@pytest.mark.django_db
def test_restore_media_uses_source_mtime(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    a = _drive_asset(tmp_path, 1)
    source_mtime = int(os.path.getmtime(a.download_path))
    items = resolve_export_items("selection", media_ids=[a.pk])

    results = restore_items(items, dest_subdir="job1")
    assert int(os.path.getmtime(results[0]["dest_path"])) == source_mtime


# ── conflict handling ──────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_conflict_skip_leaves_existing_file_untouched(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    m = _gmail_msg(tmp_path, 1, content=b"original")
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    restore_items(items, dest_subdir="job1")

    m.raw_path = str(tmp_path / "msg1.eml")  # unchanged path, but source content differs now
    open(m.raw_path, "wb").write(b"changed")
    items2 = resolve_export_items("selection", gmail_ids=[m.pk])
    results = restore_items(items2, dest_subdir="job1", on_conflict="skip")

    assert results[0]["action"] == "skipped"
    assert open(results[0]["dest_path"], "rb").read() == b"original"


@pytest.mark.django_db
def test_conflict_overwrite_replaces_existing_file(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    m = _gmail_msg(tmp_path, 1, content=b"v1")
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    restore_items(items, dest_subdir="job1")

    open(m.raw_path, "wb").write(b"v2")
    results = restore_items(items, dest_subdir="job1", on_conflict="overwrite")

    assert results[0]["action"] == "overwritten"
    assert open(results[0]["dest_path"], "rb").read() == b"v2"


@pytest.mark.django_db
def test_conflict_rename_keeps_both_files(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    m = _gmail_msg(tmp_path, 1, content=b"v1")
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    restore_items(items, dest_subdir="job1")

    open(m.raw_path, "wb").write(b"v2")
    results = restore_items(items, dest_subdir="job1", on_conflict="rename")

    assert results[0]["action"] == "renamed"
    assert results[0]["dest_path"] != os.path.join(resolve_dest_root("job1"), items[0]["arcname"])
    assert open(results[0]["dest_path"], "rb").read() == b"v2"


@pytest.mark.django_db
def test_conflict_compare_skips_when_sha256_equal(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    m = _gmail_msg(tmp_path, 1, content=b"same content")
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    restore_items(items, dest_subdir="job1")

    results = restore_items(items, dest_subdir="job1", on_conflict="compare")
    assert results[0]["action"] == "skipped"


@pytest.mark.django_db
def test_conflict_compare_renames_when_sha256_differs(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    m = _gmail_msg(tmp_path, 1, content=b"original")
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    restore_items(items, dest_subdir="job1")

    open(m.raw_path, "wb").write(b"different bytes")
    results = restore_items(items, dest_subdir="job1", on_conflict="compare")
    assert results[0]["action"] == "renamed"


def test_restore_items_rejects_bad_conflict_mode():
    with pytest.raises(ValueError):
        restore_items([], dest_subdir="x", on_conflict="bogus")


# ── restore smoke test task ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_smoke_test_passes_and_cleans_up(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    _gmail_msg(tmp_path, 1)
    from core.tasks import task_restore_smoke_test
    result = task_restore_smoke_test()

    run = IntegrityRun.objects.get(pk=result["integrity_run_id"])
    assert run.sampled == 1 and run.ok == 1 and run.mismatched == 0
    assert list((tmp_path / "restores" / "_smoke_test").iterdir()) == []


@pytest.mark.django_db
def test_smoke_test_no_candidates(tmp_path, settings):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    from core.tasks import task_restore_smoke_test
    result = task_restore_smoke_test()
    run = IntegrityRun.objects.get(pk=result["integrity_run_id"])
    assert run.sampled == 0


@pytest.mark.django_db
def test_smoke_test_records_mismatch(tmp_path, settings, monkeypatch):
    settings.RESTORE_ROOT = str(tmp_path / "restores")
    _gmail_msg(tmp_path, 1)

    import core.restore as restore_mod
    import core.tasks as tasks_mod
    real_sha256 = sha256_file
    calls = {"n": 0}

    def fake_sha256(path):
        calls["n"] += 1
        return real_sha256(path) if calls["n"] == 1 else "0" * 64

    monkeypatch.setattr(restore_mod, "sha256_file", fake_sha256)
    result = tasks_mod.task_restore_smoke_test()

    run = IntegrityRun.objects.get(pk=result["integrity_run_id"])
    assert run.mismatched == 1 and run.ok == 0
