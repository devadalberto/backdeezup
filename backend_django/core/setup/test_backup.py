"""Wizard test backup (Phase 30 step 6).

Runs discover -> download -> verify for the chosen services with a small
limit, via the SAME management commands the CLI and Makefile use (call_command
-- mockable through the same services_google/services_gmail fixtures as their
own tests), synchronously so the wizard can show a result in one request
instead of polling a Celery task.

"Backup is working" (per the plan, until Phase 31's formal verification report
exists) means at least one test item reached VERIFIED: downloaded, checksummed
and its file confirmed on disk -- exactly what the existing verify step
already checks, so no new success definition is introduced here.
"""
from django.core.management import call_command
from django.utils import timezone

from core.errors import humanize_error

_PIPELINE_STEPS = {
    "drive": [("discover", {}), ("download", {}), ("verify", {})],
    "photos": [("discover-photos", {}), ("download-photos", {}), ("verify", {})],
}


def _run_drive_pipeline(service, limit):
    for step, extra in _PIPELINE_STEPS[service]:
        kwargs = {"limit": limit, **extra} if step not in ("discover", "discover-photos") else {
            "max_pages": 1, "page_size": limit,
        }
        call_command("drive_pipeline", step, **kwargs)


def _run_gmail_pipeline(limit):
    call_command("gmail_pipeline", "discover", max_pages=1, page_size=limit)
    call_command("gmail_pipeline", "download", limit=limit, workers=2)
    call_command("gmail_pipeline", "verify", limit=limit)


def run_test_backup(services, limit=10):
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    started_at = timezone.now()
    errors = []

    for service in ("drive", "photos"):
        if service in services:
            try:
                _run_drive_pipeline(service, limit)
            except Exception as exc:
                info = humanize_error(exc)
                errors.append({"source": service.capitalize(), **info})

    if "gmail" in services:
        try:
            _run_gmail_pipeline(limit)
        except Exception as exc:
            info = humanize_error(exc)
            errors.append({"source": "Gmail", **info})

    drive_qs = DriveAsset.objects.filter(discovered_at__gte=started_at)
    gmail_qs = GmailMessage.objects.filter(discovered_at__gte=started_at)
    drive_verified = drive_qs.filter(state=DriveAsset.State.VERIFIED).count()
    gmail_verified = gmail_qs.filter(state=GmailMessage.State.VERIFIED).count()
    discovered = drive_qs.count() + gmail_qs.count()
    verified = drive_verified + gmail_verified

    return {
        "started_at": started_at.isoformat(),
        "services": services,
        "discovered": discovered,
        "verified": verified,
        "drive": {"discovered": drive_qs.count(), "verified": drive_verified},
        "gmail": {"discovered": gmail_qs.count(), "verified": gmail_verified},
        "errors": errors,
        "success": verified > 0,
    }
