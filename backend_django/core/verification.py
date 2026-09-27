"""Verification report + "backed up" success definition (Phase 31). Read-only.

An item counts as backed up only once it has been independently verified AND
still has a local file. That is ``VERIFIED`` for both models, plus whichever
later states mean "the source copy was cleaned up but the local backup was
already verified first" -- confirmed against the state machines in
docs/states.md and the precedent in google_gmail_backup's
``empty_gmail_trash`` safety check (it already treats VERIFIED/TRASHED/
SOFT_DELETED/DELETED as "accounted for").

This module never writes to DriveAsset / GmailMessage -- it only reads them
and the IntegrityRun table that ``core.tasks.task_integrity_check`` writes.
"""
import os

from django.utils import timezone

# States that mean "this item has a verified local backup", per model.
DRIVE_BACKED_UP_STATES = ("VERIFIED", "DELETE_PENDING", "DELETED")
GMAIL_BACKED_UP_STATES = ("VERIFIED", "TRASHED", "SOFT_DELETED", "DELETED")


def _missing_on_disk(paths):
    """paths: iterable of non-empty path strings. Returns count of ones that don't exist."""
    return sum(1 for p in paths if p and not os.path.exists(p))


def _drive_summary():
    from google_media_backup.models import DriveAsset

    backed_up = DriveAsset.objects.filter(state__in=DRIVE_BACKED_UP_STATES)
    oldest = backed_up.order_by("discovered_at").values_list("discovered_at", flat=True).first()
    missing = _missing_on_disk(backed_up.exclude(download_path="").values_list("download_path", flat=True))
    return {
        "backed_up": backed_up.count(),
        "missing_on_disk": missing,
        "oldest_verified": oldest,
    }


def _gmail_summary():
    from google_gmail_backup.models import GmailMessage

    backed_up = GmailMessage.objects.filter(state__in=GMAIL_BACKED_UP_STATES)
    oldest = backed_up.order_by("discovered_at").values_list("discovered_at", flat=True).first()
    missing = _missing_on_disk(backed_up.exclude(raw_path="").values_list("raw_path", flat=True))
    return {
        "backed_up": backed_up.count(),
        "missing_on_disk": missing,
        "oldest_verified": oldest,
    }


def _latest_integrity_run():
    from core.models import IntegrityRun

    run = IntegrityRun.objects.order_by("-started_at").first()
    if run is None:
        return None
    return {
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "sampled": run.sampled,
        "ok": run.ok,
        "missing": run.missing,
        "mismatched": run.mismatched,
        "details": run.details,
    }


def build_report():
    """Everything the /dashboard/verification/ page shows. Each section is a DB
    query or a disk stat -- nothing invented, nothing recomputed by re-hashing
    (that heavy lifting is task_integrity_check's job, on a sample, not this
    page's, on every item)."""
    drive = _drive_summary()
    gmail = _gmail_summary()
    return {
        "drive": drive,
        "gmail": gmail,
        "total_backed_up": drive["backed_up"] + gmail["backed_up"],
        "total_missing_on_disk": drive["missing_on_disk"] + gmail["missing_on_disk"],
        "latest_integrity_run": _latest_integrity_run(),
        "generated_at": timezone.now(),
    }
