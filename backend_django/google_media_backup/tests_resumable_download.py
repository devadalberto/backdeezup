"""Phase 42 -- resumable downloads for files >= RESUME_MIN_MB.

No network, no DB: services_google._authed_creds and AuthorizedSession are
monkeypatched with a fake session that scripts a sequence of responses
(including exceptions), matching this repo's existing mock-the-Google-edge
convention (Phase 6).
"""
from unittest.mock import patch

import pytest

import google_media_backup.services_google as sg


class _FakeResponse:
    def __init__(self, status_code, chunks=(), headers=None):
        self.status_code = status_code
        self._chunks = list(chunks)
        self.headers = headers or {}

    def iter_content(self, chunk_size=1024 * 1024):
        return iter(self._chunks)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _FakeSession:
    def __init__(self, scripted):
        self._scripted = list(scripted)
        self.calls = []

    def get(self, url, headers=None, stream=True, timeout=60):
        self.calls.append({"url": url, "headers": dict(headers or {})})
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def fake_session(monkeypatch):
    monkeypatch.setattr(sg, "_authed_creds", lambda email=None: object())
    holder = {}

    def _install(scripted):
        session = _FakeSession(scripted)
        holder["session"] = session
        monkeypatch.setattr(sg, "AuthorizedSession", lambda creds: session)
        return session

    holder["install"] = _install
    return holder


@pytest.mark.unit
def test_small_file_never_calls_resumable_path(monkeypatch):
    called = []
    monkeypatch.setattr(sg, "_download_file_resumable", lambda *a, **kw: called.append(1) or True)
    monkeypatch.setattr(sg, "drive_service", lambda: None)  # forces the plain path to fail fast

    assert sg.download_file("f1", "/tmp/out.part", size_hint=1024) is False
    assert called == []


@pytest.mark.unit
def test_unknown_size_never_calls_resumable_path(monkeypatch):
    called = []
    monkeypatch.setattr(sg, "_download_file_resumable", lambda *a, **kw: called.append(1) or True)
    monkeypatch.setattr(sg, "drive_service", lambda: None)

    assert sg.download_file("f1", "/tmp/out.part", size_hint=None) is False
    assert called == []


@pytest.mark.unit
def test_large_file_routes_to_resumable_path(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        sg, "_download_file_resumable",
        lambda file_id, out_path: seen.update(file_id=file_id, out_path=out_path) or True,
    )

    big = sg.RESUME_MIN_BYTES + 1
    assert sg.download_file("f1", "/tmp/out.part", size_hint=big) is True
    assert seen == {"file_id": "f1", "out_path": "/tmp/out.part"}


@pytest.mark.unit
def test_fresh_download_writes_full_content(tmp_path, fake_session):
    out = tmp_path / "big.part"
    fake_session["install"]([_FakeResponse(200, [b"hello ", b"world"])])

    assert sg._download_file_resumable("f1", str(out)) is True
    assert out.read_bytes() == b"hello world"
    assert fake_session["session"].calls[0]["headers"] == {}  # no Range on a fresh download


@pytest.mark.unit
def test_resumes_from_existing_partial_with_range_header(tmp_path, fake_session):
    out = tmp_path / "big.part"
    out.write_bytes(b"hello ")  # 6 bytes already on disk from a previous attempt
    fake_session["install"]([_FakeResponse(206, [b"world"])])

    assert sg._download_file_resumable("f1", str(out)) is True
    assert out.read_bytes() == b"hello world"
    assert fake_session["session"].calls[0]["headers"] == {"Range": "bytes=6-"}


@pytest.mark.unit
def test_server_ignoring_range_falls_back_to_overwrite(tmp_path, fake_session):
    out = tmp_path / "big.part"
    out.write_bytes(b"hello ")
    # Server ignores Range and sends 200 (full body) instead of 206 -- must not append.
    fake_session["install"]([_FakeResponse(200, [b"complete file"])])

    assert sg._download_file_resumable("f1", str(out)) is True
    assert out.read_bytes() == b"complete file"


@pytest.mark.unit
def test_416_at_full_size_is_treated_as_already_complete(tmp_path, fake_session):
    out = tmp_path / "big.part"
    out.write_bytes(b"already all here")
    fake_session["install"]([_FakeResponse(416)])

    assert sg._download_file_resumable("f1", str(out)) is True
    assert out.read_bytes() == b"already all here"  # untouched


@pytest.mark.unit
def test_network_error_preserves_partial_file_and_retries(tmp_path, fake_session):
    out = tmp_path / "big.part"
    out.write_bytes(b"hello ")
    import requests
    fake_session["install"]([requests.exceptions.ConnectionError("dropped"), _FakeResponse(206, [b"world"])])

    with patch("time.sleep"):
        assert sg._download_file_resumable("f1", str(out)) is True
    assert out.read_bytes() == b"hello world"


@pytest.mark.unit
def test_gives_up_after_max_retries_without_deleting_partial(tmp_path, fake_session):
    out = tmp_path / "big.part"
    out.write_bytes(b"hello ")
    import requests
    fake_session["install"]([requests.exceptions.ConnectionError("dropped")] * 4)

    with patch("time.sleep"):
        assert sg._download_file_resumable("f1", str(out)) is False
    assert out.read_bytes() == b"hello "  # never deleted -- next run can still resume


@pytest.mark.unit
def test_no_creds_returns_false(monkeypatch, tmp_path):
    monkeypatch.setattr(sg, "_authed_creds", lambda email=None: None)
    assert sg._download_file_resumable("f1", str(tmp_path / "x.part")) is False


@pytest.mark.unit
def test_download_or_export_file_forwards_size_hint_for_plain_downloads(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        sg, "download_file",
        lambda file_id, out_path, size_hint=None: seen.update(size_hint=size_hint) or True,
    )
    assert sg.download_or_export_file("f1", "image/jpeg", "/tmp/x", size_hint=999) is True
    assert seen == {"size_hint": 999}


@pytest.mark.unit
def test_download_or_export_file_does_not_forward_size_hint_for_google_exports(monkeypatch):
    """Google Docs/Sheets/Slides exports keep their own bounded, non-resumable path."""
    called_resumable = []
    monkeypatch.setattr(sg, "_download_file_resumable", lambda *a, **kw: called_resumable.append(1))
    monkeypatch.setattr(sg, "drive_service", lambda: None)  # export branch fails fast, never resumable

    result = sg.download_or_export_file(
        "f1", "application/vnd.google-apps.document", "/tmp/x", size_hint=sg.RESUME_MIN_BYTES + 1,
    )
    assert result is False
    assert called_resumable == []


@pytest.mark.unit
def test_download_photos_item_forwards_size_hint(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        sg, "download_file",
        lambda file_id, out_path, size_hint=None: seen.update(size_hint=size_hint) or True,
    )
    assert sg.download_photos_item("f1", "/tmp/x", size_hint=42) is True
    assert seen == {"size_hint": 42}


@pytest.mark.django_db
def test_task_photos_download_batch_passes_db_size_bytes_as_size_hint(monkeypatch):
    """End-to-end wiring check: the DriveAsset.size_bytes discovered earlier is
    what decides resumability, not a value re-derived at download time."""
    from google_media_backup.models import DriveAsset
    from google_media_backup import tasks as media_tasks

    big = DriveAsset.objects.create(
        drive_id="photos:abc123", name="movie.mp4", mime_type="video/mp4",
        state="DISCOVERED", size_bytes=sg.RESUME_MIN_BYTES + 1,
    )

    seen = {}

    def fake_download_photos_item(raw_id, tmp, size_hint=None):
        seen["size_hint"] = size_hint
        with open(tmp, "wb") as fh:
            fh.write(b"data")
        return True

    # task_photos_download_batch does `from .services_google import
    # download_photos_item` *inside* the function body, so the name is
    # resolved from services_google at call time -- patch it there, not on
    # the tasks module (which never gets its own module-level attribute).
    monkeypatch.setattr(sg, "download_photos_item", fake_download_photos_item)

    result = media_tasks.task_photos_download_batch(limit=10)

    assert result["downloaded"] == 1
    assert seen["size_hint"] == big.size_bytes
