"""Unit tests for google_gmail_backup.schemas — no DB, no network."""
import pytest


@pytest.mark.unit
class TestMetadataSnapshot:
    def test_full_construction(self):
        from .schemas import MetadataSnapshot
        s = MetadataSnapshot(
            subject="Test",
            from_address="test@example.com",
            to_address="me@test.com",
            date="2026-06-03 12:00:00+00:00",
            labels=["INBOX"],
            size_estimate=1024,
        )
        d = s.model_dump()
        assert d["subject"] == "Test"
        assert d["from_address"] == "test@example.com"
        assert d["size_estimate"] == 1024

    def test_defaults_on_empty(self):
        from .schemas import MetadataSnapshot
        s = MetadataSnapshot()
        assert s.subject == ""
        assert s.labels == []
        assert s.size_estimate == 0
        assert s.date is None

    def test_roundtrip(self):
        from .schemas import MetadataSnapshot
        original = {"subject": "Hi", "from_address": "a@b.com",
                    "to_address": "", "date": None, "labels": ["INBOX"], "size_estimate": 512}
        s = MetadataSnapshot(**original)
        assert s.model_dump() == original

    def test_extra_fields_ignored(self):
        from .schemas import MetadataSnapshot
        s = MetadataSnapshot(subject="Hi", unknown_field="ignored")
        assert not hasattr(s, "unknown_field")

    def test_none_labels_coerced_to_list(self):
        from .schemas import MetadataSnapshot
        s = MetadataSnapshot(labels=None)
        assert s.labels == []

    def test_size_estimate_coercion(self):
        from .schemas import MetadataSnapshot
        s = MetadataSnapshot(size_estimate="512")
        assert s.size_estimate == 512
        s2 = MetadataSnapshot(size_estimate=None)
        assert s2.size_estimate == 0

    def test_snapshot_from_message_uses_schema(self):
        from unittest.mock import MagicMock
        from django.utils import timezone
        from .schemas import snapshot_from_message
        msg = MagicMock()
        msg.subject = "Hello"
        msg.from_address = "sender@example.com"
        msg.to_address = "me@test.com"
        msg.date = timezone.now()
        msg.labels = ["INBOX", "IMPORTANT"]
        msg.size_estimate = 2048
        result = snapshot_from_message(msg)
        assert result["subject"] == "Hello"
        assert result["from_address"] == "sender@example.com"
        assert result["size_estimate"] == 2048
        assert isinstance(result["labels"], list)
        assert isinstance(result["date"], str)
