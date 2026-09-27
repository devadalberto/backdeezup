"""Phase 36 — export to ZIP/TAR. Isolated, no Google network calls: everything
here is real local files (tmp_path) plus real DB rows, no mocked Gmail/Drive API.
"""
import hashlib
import json
import os
import tarfile
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.export import (
    async_item_threshold, iter_archive_stream, resolve_export_items, write_archive_to_file,
)
from core.models import ExportJob
from google_gmail_backup.models import GmailMessage
from google_media_backup.models import DriveAsset


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _gmail_msg(tmp_path, i, content=b"hello eml"):
    p = tmp_path / f"msg{i}.eml"
    p.write_bytes(content)
    return GmailMessage.objects.create(
        gmail_id=f"g{i}", thread_id=f"t{i}", subject=f"s{i}",
        from_address="a@example.com", date=timezone.now(),
        state=GmailMessage.STATE_VERIFIED, account_email="me@test.com",
        raw_path=str(p), sha256=_sha256(content),
    )


def _drive_asset(tmp_path, i, content=b"hello drive file"):
    p = tmp_path / f"asset{i}.bin"
    p.write_bytes(content)
    return DriveAsset.objects.create(
        drive_id=f"d{i}", name=f"file{i}.bin", mime_type="application/octet-stream",
        size_bytes=len(content), state=DriveAsset.State.VERIFIED, download_path=str(p),
    )


# ── resolve_export_items ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_resolve_selection_gmail_and_media(tmp_path):
    m = _gmail_msg(tmp_path, 1)
    a = _drive_asset(tmp_path, 1)
    items = resolve_export_items("selection", gmail_ids=[m.pk], media_ids=[a.pk])
    kinds = {i["kind"] for i in items}
    assert kinds == {"gmail", "media"}
    assert len(items) == 2


@pytest.mark.django_db
def test_resolve_selection_requires_ids():
    with pytest.raises(ValueError):
        resolve_export_items("selection")


@pytest.mark.django_db
def test_resolve_skips_missing_file_on_disk(tmp_path):
    m = _gmail_msg(tmp_path, 1)
    m.raw_path = str(tmp_path / "does-not-exist.eml")
    m.save(update_fields=["raw_path"])
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    assert items == []


@pytest.mark.django_db
def test_resolve_source_gmail_only(tmp_path):
    _gmail_msg(tmp_path, 1)
    _drive_asset(tmp_path, 1)
    items = resolve_export_items("source", source="gmail")
    assert all(i["kind"] == "gmail" for i in items)
    assert len(items) == 1


@pytest.mark.django_db
def test_resolve_source_requires_valid_source():
    with pytest.raises(ValueError):
        resolve_export_items("source", source="bogus")


@pytest.mark.django_db
def test_resolve_everything_includes_both_sources(tmp_path):
    _gmail_msg(tmp_path, 1)
    _drive_asset(tmp_path, 1)
    items = resolve_export_items("everything")
    assert {i["kind"] for i in items} == {"gmail", "media"}


@pytest.mark.django_db
def test_resolve_unknown_scope_raises():
    with pytest.raises(ValueError):
        resolve_export_items("bogus-scope")


# ── streaming archive: round-trip sha256 verification ────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize("fmt", ["zip", "tar"])
def test_stream_archive_roundtrip_sha256_matches(tmp_path, fmt):
    m = _gmail_msg(tmp_path, 1, content=b"gmail body one")
    a = _drive_asset(tmp_path, 1, content=b"drive body two")
    items = resolve_export_items("selection", gmail_ids=[m.pk], media_ids=[a.pk])

    archive_bytes = b"".join(iter_archive_stream(items, fmt))
    out_dir = tmp_path / f"extract-{fmt}"
    out_dir.mkdir()

    if fmt == "zip":
        archive_path = tmp_path / "out.zip"
        archive_path.write_bytes(archive_bytes)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(out_dir)
            names = zf.namelist()
    else:
        archive_path = tmp_path / "out.tar.gz"
        archive_path.write_bytes(archive_bytes)
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(out_dir)
            names = tf.getnames()

    assert "manifest.json" in names
    manifest = json.loads((out_dir / "manifest.json").read_text())["files"]
    assert len(manifest) == 2
    for entry in manifest:
        on_disk = (out_dir / entry["path"]).read_bytes()
        assert _sha256(on_disk) == entry["sha256"]
        assert len(on_disk) == entry["size"]


@pytest.mark.django_db
def test_write_archive_to_file_matches_manifest(tmp_path):
    m = _gmail_msg(tmp_path, 1, content=b"on-disk body")
    items = resolve_export_items("selection", gmail_ids=[m.pk])
    dest = tmp_path / "export.zip"
    manifest = write_archive_to_file(items, "zip", str(dest))
    assert len(manifest) == 1
    with zipfile.ZipFile(dest) as zf:
        data = zf.read(manifest[0]["path"])
    assert _sha256(data) == manifest[0]["sha256"]


# ── dashboard_export view: sync vs async threshold ────────────────────────────

@pytest.fixture
def staff_client(client, db, settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "export-test"}}
    user = get_user_model().objects.create_user("staff", password="x", is_staff=True)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_export_view_streams_small_source_scope(staff_client, tmp_path):
    _gmail_msg(tmp_path, 1)
    resp = staff_client.post("/dashboard/export/", {"scope": "source", "source": "gmail", "format": "zip"})
    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith("attachment;")
    assert ExportJob.objects.count() == 0


@pytest.mark.django_db
def test_export_view_everything_always_goes_async(staff_client, tmp_path, settings):
    _gmail_msg(tmp_path, 1)
    with patch("core.tasks.task_run_export.delay", return_value=MagicMock(id="x")) as delay:
        resp = staff_client.post("/dashboard/export/", {"scope": "everything", "format": "zip"})
    assert resp.status_code == 200
    assert resp.json()["async"] is True
    assert ExportJob.objects.count() == 1
    delay.assert_called_once()


@pytest.mark.django_db
def test_export_view_source_over_threshold_goes_async(staff_client, tmp_path, settings):
    settings.EXPORT_ASYNC_THRESHOLD = 1
    _gmail_msg(tmp_path, 1)
    _gmail_msg(tmp_path, 2)
    with patch("core.tasks.task_run_export.delay", return_value=MagicMock(id="x")):
        resp = staff_client.post("/dashboard/export/", {"scope": "source", "source": "gmail", "format": "zip"})
    assert resp.json()["async"] is True


@pytest.mark.django_db
def test_export_view_rejects_bad_scope(staff_client):
    resp = staff_client.post("/dashboard/export/", {"scope": "selection", "format": "zip"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_export_view_nothing_to_export(staff_client):
    resp = staff_client.post("/dashboard/export/", {"scope": "source", "source": "gmail", "format": "zip"})
    assert resp.status_code == 404


# ── async task ─────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_task_run_export_writes_file_and_marks_done(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    m = _gmail_msg(tmp_path, 1, content=b"async body")
    job = ExportJob.objects.create(
        scope="everything", format="zip", item_count=1, item_ids={"gmail": [m.pk], "media": []},
    )
    from core.tasks import task_run_export
    task_run_export(job.id)

    job.refresh_from_db()
    assert job.status == ExportJob.Status.DONE
    assert os.path.exists(job.file_path)
    with zipfile.ZipFile(job.file_path) as zf:
        assert "manifest.json" in zf.namelist()


@pytest.mark.django_db
def test_task_run_export_marks_error_on_bad_format(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    m = _gmail_msg(tmp_path, 1)
    job = ExportJob.objects.create(
        scope="everything", format="bogus", item_count=1, item_ids={"gmail": [m.pk], "media": []},
    )
    from core.tasks import task_run_export
    task_run_export(job.id)
    job.refresh_from_db()
    assert job.status == ExportJob.Status.ERROR
    assert job.error


# ── admin "Export selected" actions ───────────────────────────────────────────

@pytest.mark.django_db
def test_admin_export_action_streams_zip(tmp_path):
    from django.contrib.admin.sites import AdminSite
    from google_gmail_backup.admin import GmailMessageAdmin

    m = _gmail_msg(tmp_path, 1)
    admin_instance = GmailMessageAdmin(GmailMessage, AdminSite())
    resp = admin_instance.action_export_zip(None, GmailMessage.objects.filter(pk=m.pk))
    assert resp.status_code == 200
    assert resp["Content-Disposition"].startswith("attachment;")


def test_async_item_threshold_reads_setting(settings):
    settings.EXPORT_ASYNC_THRESHOLD = 42
    assert async_item_threshold() == 42
