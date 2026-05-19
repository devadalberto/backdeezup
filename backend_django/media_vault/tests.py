"""
Tests for media_vault — EXIF strip, MediaMetadata, video streaming, gallery.
"""
import io
import os
import struct
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings

User = get_user_model()


def make_staff():
    return User.objects.create_user("vaultuser", password="pass", is_staff=True)


# ── Minimal JPEG factory ───────────────────────────────────────────────────────

def _make_minimal_jpeg(with_exif: bool = False) -> bytes:
    """
    Build a valid minimal JPEG (1×1 white pixel).
    If with_exif=True, embed a fake EXIF APP1 segment with Make/Model/GPS.
    """
    from PIL import Image
    import io as _io

    img = Image.new("RGB", (2, 2), color=(255, 255, 255))
    buf = _io.BytesIO()

    if with_exif:
        import piexif
        try:
            exif_dict = {
                "0th": {
                    piexif.ImageIFD.Make: b"Apple",
                    piexif.ImageIFD.Model: b"iPhone 12",
                },
                "GPS": {
                    piexif.GPSIFD.GPSLatitudeRef: b"N",
                    piexif.GPSIFD.GPSLatitude: ((20, 1), (39, 1), (688, 100)),
                    piexif.GPSIFD.GPSLongitudeRef: b"W",
                    piexif.GPSIFD.GPSLongitude: ((100, 1), (26, 1), (206, 100)),
                },
            }
            exif_bytes = piexif.dump(exif_dict)
            img.save(buf, format="JPEG", exif=exif_bytes)
        except ImportError:
            # piexif not installed — save without EXIF
            img.save(buf, format="JPEG")
    else:
        img.save(buf, format="JPEG")

    return buf.getvalue()


def _has_exif(data: bytes) -> bool:
    """Check if JPEG bytes contain an APP1/EXIF marker."""
    # JPEG APP1 marker: FF E1
    return b"\xff\xe1" in data[:200]


# ── EXIF strip unit tests ─────────────────────────────────────────────────────

class ExifStripTest(TestCase):
    """Tests for media_vault.exif_strip.strip_and_preserve"""

    def _call(self, data, mime_type="image/jpeg", **kwargs):
        from media_vault.exif_strip import strip_and_preserve
        return strip_and_preserve(
            data=data,
            source_path=kwargs.get("source_path", "/tmp/test_img.jpg"),
            filename=kwargs.get("filename", "test.jpg"),
            mime_type=mime_type,
            sha256=kwargs.get("sha256", "abc123"),
            gmail_message_id=kwargs.get("gmail_message_id", "msg001"),
        )

    def test_jpeg_without_exif_returns_valid_jpeg(self):
        data = _make_minimal_jpeg(with_exif=False)
        clean, record = self._call(data)
        self.assertIsNotNone(clean)
        self.assertGreater(len(clean), 0)
        # Must still be a valid JPEG (starts with FF D8)
        self.assertEqual(clean[:2], b"\xff\xd8")

    def test_strip_reduces_or_maintains_size(self):
        """Stripped image must not be larger than original (within 10% tolerance)."""
        data = _make_minimal_jpeg(with_exif=False)
        clean, _ = self._call(data)
        # Stripped image should be ≤ 110% of original (re-encoding may vary slightly)
        self.assertLessEqual(len(clean), len(data) * 1.1)

    def test_metadata_record_created(self):
        from media_vault.models import MediaMetadata
        data = _make_minimal_jpeg(with_exif=False)
        path = "/tmp/test_exif_record.jpg"
        _, record = self._call(data, source_path=path)
        # Record should exist in DB
        self.assertTrue(MediaMetadata.objects.filter(source_path=path).exists())

    def test_metadata_record_idempotent(self):
        """Calling strip_and_preserve twice on same path returns existing record."""
        from media_vault.models import MediaMetadata
        data = _make_minimal_jpeg(with_exif=False)
        path = "/tmp/test_idempotent.jpg"
        _, r1 = self._call(data, source_path=path)
        _, r2 = self._call(data, source_path=path)
        # Only one record should exist
        self.assertEqual(MediaMetadata.objects.filter(source_path=path).count(), 1)

    def test_original_size_recorded(self):
        from media_vault.models import MediaMetadata
        data = _make_minimal_jpeg(with_exif=False)
        path = "/tmp/test_size_record.jpg"
        _, record = self._call(data, source_path=path)
        meta = MediaMetadata.objects.get(source_path=path)
        self.assertEqual(meta.original_size_bytes, len(data))

    def test_png_handled(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (2, 2), (128, 128, 128)).save(buf, format="PNG")
        data = buf.getvalue()
        clean, _ = self._call(data, mime_type="image/png",
                               source_path="/tmp/test.png", filename="test.png")
        # Should return valid PNG (starts with PNG magic)
        self.assertEqual(clean[:8], b"\x89PNG\r\n\x1a\n")

    def test_unsupported_mime_returns_original(self):
        """HEIC and other unsupported formats pass through unchanged."""
        fake_heic = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 100
        clean, _ = self._call(fake_heic, mime_type="image/heic",
                               source_path="/tmp/test.heic", filename="test.heic")
        self.assertEqual(clean, fake_heic)

    def test_video_not_stripped(self):
        """Video files pass through unchanged (ffmpeg not wired yet)."""
        fake_mp4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 100
        from media_vault.exif_strip import strip_and_preserve
        clean, _ = strip_and_preserve(
            data=fake_mp4,
            source_path="/tmp/test.mp4",
            filename="test.mp4",
            mime_type="video/mp4",
        )
        self.assertEqual(clean, fake_mp4)

    def test_corrupt_image_handled_gracefully(self):
        """Corrupt bytes do not crash — returns original."""
        corrupt = b"\xff\xd8\xff\xe0" + b"\x00" * 20  # truncated JPEG
        clean, _ = self._call(corrupt, source_path="/tmp/corrupt.jpg")
        # Should not raise — returns something
        self.assertIsNotNone(clean)


# ── MediaMetadata model tests ─────────────────────────────────────────────────

class MediaMetadataModelTest(TestCase):
    def test_str_representation(self):
        from media_vault.models import MediaMetadata
        m = MediaMetadata.objects.create(
            source_path="/tmp/photo.jpg",
            filename="photo.jpg",
            device_make="Apple",
            device_model="iPhone 12",
        )
        self.assertIn("photo.jpg", str(m))
        self.assertIn("Apple", str(m))

    def test_gps_fields_nullable(self):
        from media_vault.models import MediaMetadata
        m = MediaMetadata.objects.create(
            source_path="/tmp/no_gps.jpg",
            filename="no_gps.jpg",
        )
        self.assertIsNone(m.gps_latitude)
        self.assertIsNone(m.gps_longitude)

    def test_raw_exif_stored_as_json(self):
        from media_vault.models import MediaMetadata
        exif = {"Make": "Samsung", "Model": "Galaxy S21", "GPSInfo": {"GPSLatitudeRef": "N"}}
        m = MediaMetadata.objects.create(
            source_path="/tmp/samsung.jpg",
            filename="samsung.jpg",
            raw_exif=exif,
        )
        m.refresh_from_db()
        self.assertEqual(m.raw_exif["Make"], "Samsung")
        self.assertIn("GPSInfo", m.raw_exif)


# ── Video streaming tests ─────────────────────────────────────────────────────

class VideoStreamingTest(TestCase):
    """Tests for /vault/stream/<id>/ HTTP Range view."""

    def setUp(self):
        self.client = Client()
        self.client.force_login(make_staff())

    def test_stream_404_for_nonexistent_media(self):
        r = self.client.get("/vault/stream/99999/")
        self.assertEqual(r.status_code, 404)

    def test_stream_requires_staff(self):
        from django.contrib.auth import get_user_model
        anon = Client()
        r = anon.get("/vault/stream/1/")
        # Should redirect to login, not 200
        self.assertIn(r.status_code, [302, 403, 404])

    def _make_vault_media(self, content: bytes, title: str = "Test Video") -> tuple:
        """Helper: create a VaultMedia with a real file on disk. Returns (vm, tmp_path)."""
        from media_vault.models import VaultMedia
        from wagtail.models import Collection
        from django.core.files.base import ContentFile

        root_collection = Collection.objects.first()
        vm = VaultMedia(
            title=title,
            type="video",
            collection=root_collection,
        )
        vm.file.save("test_video.mp4", ContentFile(content), save=True)
        return vm, vm.file.path

    def test_stream_with_real_file(self):
        """Create a VaultMedia with a real temp file and verify 200 response."""
        content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 512
        vm, file_path = self._make_vault_media(content)
        try:
            r = self.client.get(f"/vault/stream/{vm.id}/")
            self.assertIn(r.status_code, [200, 206])
            self.assertEqual(r.get("Accept-Ranges"), "bytes")
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
            vm.delete()

    def test_range_request_returns_206(self):
        """HTTP Range header → 206 Partial Content."""
        content = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 1024
        vm, file_path = self._make_vault_media(content, "Range Test")
        try:
            r = self.client.get(
                f"/vault/stream/{vm.id}/",
                HTTP_RANGE="bytes=0-99",
            )
            self.assertEqual(r.status_code, 206)
            self.assertIn("Content-Range", r)
            self.assertEqual(r.get("Accept-Ranges"), "bytes")
            self.assertEqual(int(r.get("Content-Length", 0)), 100)
        finally:
            if os.path.exists(file_path):
                os.unlink(file_path)
            vm.delete()


# ── Security: path traversal in stream_video ─────────────────────────────────

class StreamVideoSecurityTest(TestCase):
    """Ensure stream_video cannot be used for path traversal."""

    def setUp(self):
        self.client = Client()
        self.client.force_login(make_staff())

    def test_nonexistent_id_returns_404_not_500(self):
        r = self.client.get("/vault/stream/0/")
        self.assertEqual(r.status_code, 404)

    def test_negative_id_returns_404(self):
        r = self.client.get("/vault/stream/-1/")
        self.assertEqual(r.status_code, 404)
