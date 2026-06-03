"""Unit tests for google_media_backup — no DB, no network."""
import os
import tempfile
import pytest


@pytest.mark.unit
class TestDeterministicPath:
    def test_image_path_structure(self, tmp_path, monkeypatch):
        import google_media_backup.utils as utils
        monkeypatch.setattr(utils, "MEDIA_ROOT", tmp_path)
        path = utils.deterministic_path("photo.jpg", "abcdef1234567890", kind="image")
        assert "/image/" in path
        assert "/abcd/" in path
        assert "/ab/" in path
        assert path.endswith(".jpg")

    def test_document_path_structure(self, tmp_path, monkeypatch):
        import google_media_backup.utils as utils
        monkeypatch.setattr(utils, "MEDIA_ROOT", tmp_path)
        path = utils.deterministic_path("report.pdf", "deadbeef00112233", kind="document")
        assert "/document/" in path
        assert "/dead/" in path
        assert "/de/" in path
        assert path.endswith(".pdf")

    def test_video_path_structure(self, tmp_path, monkeypatch):
        import google_media_backup.utils as utils
        monkeypatch.setattr(utils, "MEDIA_ROOT", tmp_path)
        path = utils.deterministic_path("clip.mp4", "1234abcd5678efgh", kind="video")
        assert "/video/" in path


@pytest.mark.unit
class TestSha256File:
    def test_known_content(self):
        from google_media_backup.utils import sha256_file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello world")
            f.flush()
            digest = sha256_file(f.name)
        os.unlink(f.name)
        assert digest == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"


@pytest.mark.unit
class TestGoogleExportMap:
    def test_all_google_native_types_have_export(self):
        from google_media_backup.services_google import GOOGLE_EXPORT_MAP, _GOOGLE_NATIVE_MIMES
        for mime in _GOOGLE_NATIVE_MIMES:
            assert mime in GOOGLE_EXPORT_MAP
            export_mime, ext = GOOGLE_EXPORT_MAP[mime]
            assert export_mime.startswith("application/")
            assert ext.startswith(".")

    def test_docs_export_to_pdf(self):
        from google_media_backup.services_google import GOOGLE_EXPORT_MAP
        mime, ext = GOOGLE_EXPORT_MAP["application/vnd.google-apps.document"]
        assert mime == "application/pdf"
        assert ext == ".pdf"

    def test_sheets_export_to_xlsx(self):
        from google_media_backup.services_google import GOOGLE_EXPORT_MAP
        _, ext = GOOGLE_EXPORT_MAP["application/vnd.google-apps.spreadsheet"]
        assert ext == ".xlsx"


@pytest.mark.unit
class TestMimeClassification:
    def test_image_mimes_complete(self):
        from media_vault.management.commands.import_media import IMAGE_MIMES
        assert "image/jpeg" in IMAGE_MIMES
        assert "image/png" in IMAGE_MIMES
        assert "image/heic" in IMAGE_MIMES

    def test_doc_mimes_includes_google_native(self):
        from media_vault.management.commands.import_media import DOC_MIMES
        assert "application/vnd.google-apps.document" in DOC_MIMES
        assert "application/vnd.google-apps.spreadsheet" in DOC_MIMES
        assert "application/pdf" in DOC_MIMES

    def test_no_overlap_between_sets(self):
        from media_vault.management.commands.import_media import IMAGE_MIMES, VIDEO_MIMES, DOC_MIMES
        assert not (IMAGE_MIMES & VIDEO_MIMES)
        assert not (IMAGE_MIMES & DOC_MIMES)
        assert not (VIDEO_MIMES & DOC_MIMES)
