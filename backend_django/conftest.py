import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DATABASE_URL"] = ""


@pytest.fixture
def mock_drive_service():
    with patch("google_media_backup.services_google.drive_service") as mock:
        svc = MagicMock()
        mock.return_value = svc
        yield svc


@pytest.fixture
def mock_photos_service():
    with patch("google_media_backup.services_google.photos_service") as mock:
        svc = MagicMock()
        mock.return_value = svc
        yield svc


@pytest.fixture
def mock_gmail_service():
    with patch("google_gmail_backup.services_gmail.gmail_service") as mock:
        svc = MagicMock()
        mock.return_value = svc
        yield svc


@pytest.fixture
def sample_drive_asset(db):
    from google_media_backup.models import DriveAsset
    def _make(**kwargs):
        defaults = {
            "drive_id": f"test_{kwargs.get('name', 'file')}_001",
            "name": "test_file.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 1024,
            "state": "DISCOVERED",
        }
        defaults.update(kwargs)
        return DriveAsset.objects.create(**defaults)
    return _make


@pytest.fixture
def sample_gmail_message(db):
    from google_gmail_backup.models import GmailMessage
    from django.utils import timezone
    def _make(**kwargs):
        defaults = {
            "gmail_id": f"test_msg_{kwargs.get('subject', 'test')[:10]}",
            "subject": "Test message",
            "from_address": "test@example.com",
            "to_address": "me@test.com",
            "date": timezone.now(),
            "labels": ["INBOX"],
            "size_estimate": 1024,
            "state": "VERIFIED",
            "account_email": "me@test.com",
        }
        defaults.update(kwargs)
        return GmailMessage.objects.create(**defaults)
    return _make
