from django.contrib.auth.models import User
from django.test import TestCase, Client

from .models import DriveAsset, MediaItem, RunLog


class DriveAssetModelTest(TestCase):
    def test_create_asset(self):
        a = DriveAsset.objects.create(
            drive_id="test123",
            name="photo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
        )
        self.assertEqual(a.state, "DISCOVERED")

    def test_state_choices(self):
        states = [s[0] for s in DriveAsset.STATE_CHOICES]
        self.assertIn("DISCOVERED", states)
        self.assertIn("DELETED", states)

    def test_media_item_dedup(self):
        m1, created1 = MediaItem.objects.get_or_create(
            sha256="abc123", defaults={"file": "imported/ab/abc123.jpg"}
        )
        m2, created2 = MediaItem.objects.get_or_create(
            sha256="abc123", defaults={"file": "imported/ab/abc123.jpg"}
        )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(m1.id, m2.id)

    def test_runlog_create(self):
        r = RunLog.objects.create(
            run_id="run-001",
            status="RUNNING",
            totals={"discovered": 5},
        )
        self.assertEqual(r.status, "RUNNING")
        self.assertEqual(r.totals["discovered"], 5)


class DriveAPITest(TestCase):
    def setUp(self):
        self.client = Client()
        user = User.objects.create_user("testuser", password="testpass")
        self.client.force_login(user)
        DriveAsset.objects.create(
            drive_id="drive1",
            name="video.mp4",
            mime_type="video/mp4",
            size_bytes=5000,
            state="DISCOVERED",
        )
        DriveAsset.objects.create(
            drive_id="drive2",
            name="image.jpg",
            mime_type="image/jpeg",
            size_bytes=2000,
            state="VERIFIED",
        )

    def test_list_assets_all(self):
        r = self.client.get("/api/assets")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    def test_list_assets_filter_state(self):
        r = self.client.get("/api/assets?state=VERIFIED")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["state"], "VERIFIED")

    def test_list_assets_filter_q(self):
        r = self.client.get("/api/assets?q=video")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "video.mp4")

    def test_swagger_ui_loads(self):
        r = self.client.get("/api/docs")
        self.assertEqual(r.status_code, 200)

    def test_sync_mark_delete_only_verified(self):
        r = self.client.post("/api/sync/mark-delete?limit=100")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["queued_for_delete"], 1)
        self.assertTrue(
            DriveAsset.objects.filter(drive_id="drive2", state="DELETE_PENDING").exists()
        )
        self.assertTrue(
            DriveAsset.objects.filter(drive_id="drive1", state="DISCOVERED").exists()
        )
