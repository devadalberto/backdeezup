"""Phase 26 — status label tests."""
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from core import dashboard
from core.labels import FAILED, SAFE_TO_DELETE, STATE_LABELS, item_label, state_label
from google_gmail_backup.models import GmailMessage
from google_media_backup.models import DriveAsset, MediaItem


def test_every_real_state_has_a_label():
    for model in (DriveAsset, GmailMessage):
        for value in model.State.values:
            assert value in STATE_LABELS, f"{model.__name__}.{value} has no label"


@pytest.mark.parametrize("state,label", [
    ("DISCOVERED", "Discovered"), ("DOWNLOADED", "Downloaded"), ("VERIFIED", "Verified"),
    ("IMPORTED", "Imported"), ("DELETE_PENDING", "Deletion pending"), ("DELETED", "Deleted remotely"),
])
def test_plan_labels(state, label):
    assert state_label(state) == label
    assert item_label(SimpleNamespace(state=state, error=""))["label"] == label


def test_unknown_state_renders_raw_no_crash():
    assert state_label("WEIRD") == "WEIRD"
    assert item_label(SimpleNamespace(state="WEIRD", error=""))["label"] == "WEIRD"
    assert item_label(SimpleNamespace())["label"] == ""


def test_error_field_means_failed():
    assert item_label(SimpleNamespace(state="DOWNLOADED", error="File missing")) == {"label": FAILED, "kind": "fail"}


def test_safe_to_delete_needs_both_proofs(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_text("x")
    ok = SimpleNamespace(state="VERIFIED", error="", download_path=str(f), media_item_id=1)
    assert item_label(ok)["label"] == SAFE_TO_DELETE
    assert item_label(SimpleNamespace(**{**vars(ok), "media_item_id": None}))["label"] == "Verified"
    assert item_label(SimpleNamespace(**{**vars(ok), "download_path": str(tmp_path / "gone")}))["label"] == "Verified"
    # only VERIFIED can be safe
    assert item_label(SimpleNamespace(**{**vars(ok), "state": "IMPORTED"}))["label"] == "Imported"


@pytest.mark.django_db
def test_recent_items_and_page_render_chips(client, tmp_path):
    f = tmp_path / "a.jpg"
    f.write_text("x")
    mi = MediaItem.objects.create(sha256="a" * 64, file="imported/a.jpg")
    DriveAsset.objects.create(drive_id="d1", name="safe.jpg", mime_type="image/jpeg", state="VERIFIED",
                              download_path=str(f), media_item=mi)
    DriveAsset.objects.create(drive_id="photos:p1", name="bad.jpg", mime_type="image/jpeg", state="DOWNLOADED", error="File missing")
    GmailMessage.objects.create(gmail_id="g1", subject="hi", account_email="a@b.c", state="TRASHED")
    rows = {r["name"]: r for r in dashboard.recent_items()["rows"]}
    assert rows["safe.jpg"]["chip"]["label"] == SAFE_TO_DELETE
    assert rows["bad.jpg"]["chip"]["label"] == FAILED and rows["bad.jpg"]["source"] == "Photos"
    assert rows["hi"]["chip"]["label"] == "In Gmail trash"

    client.force_login(get_user_model().objects.create_user("s", password="x", is_staff=True))
    html = client.get("/dashboard/cards/").content.decode()
    assert SAFE_TO_DELETE in html and "chip-fail" in html
    page = client.get("/dashboard/").content.decode()
    assert "/vault/" in page and "/admin/gmail/dashboard/" in page
    assert "/vault/" in client.get("/health/").content.decode()
