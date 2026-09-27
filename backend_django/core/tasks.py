"""Thin Celery wrappers for dashboard actions (Phase 27).

Verify and media import only existed as management commands. These wrappers call
those commands unchanged so the dashboard can enqueue them; no logic lives here.
"""
import hashlib
import os
import random

from celery import shared_task
from django.core.management import call_command


@shared_task(name="core.tasks.task_verify_files")
def task_verify_files(limit=500):
    """Run the existing Drive and Gmail verify steps."""
    call_command("drive_pipeline", "verify", limit=limit)
    call_command("gmail_pipeline", "verify", limit=limit)
    return {"verified_step": "done", "limit": limit}


@shared_task(name="core.tasks.task_import_media")
def task_import_media():
    """Run the existing import_media command (Drive/Gmail -> Media Vault)."""
    call_command("import_media")
    return {"import_media": "done"}


def _hash_file(path, algo, chunk_size=1024 * 1024):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def _sample_ids(queryset, n):
    ids = list(queryset.values_list("pk", flat=True))
    return random.sample(ids, min(n, len(ids)))


@shared_task(name="core.tasks.task_integrity_check")
def task_integrity_check(sample_size=None):
    """Re-hash a random sample of already-backed-up files against their stored
    checksum (Phase 31). READ-ONLY: only reads DriveAsset/GmailMessage files and
    stored checksums, and WRITES only its own IntegrityRun row -- it never
    flips DriveAsset.state or GmailMessage.state.
    """
    from django.conf import settings
    from django.utils import timezone

    from core.models import IntegrityRun
    from core.verification import DRIVE_BACKED_UP_STATES, GMAIL_BACKED_UP_STATES
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    n = sample_size if sample_size is not None else settings.INTEGRITY_CHECK_SAMPLE_SIZE

    drive_ids = _sample_ids(
        DriveAsset.objects.filter(state__in=DRIVE_BACKED_UP_STATES).exclude(download_path=""), n,
    )
    gmail_ids = _sample_ids(
        GmailMessage.objects.filter(state__in=GMAIL_BACKED_UP_STATES).exclude(raw_path=""), n,
    )

    ok = missing = mismatched = 0
    details = []

    for asset in DriveAsset.objects.filter(pk__in=drive_ids):
        if not os.path.exists(asset.download_path):
            missing += 1
            details.append({"source": "drive", "id": asset.pk, "path": asset.download_path, "issue": "missing"})
            continue
        if asset.md5_checksum and _hash_file(asset.download_path, "md5") != asset.md5_checksum:
            mismatched += 1
            details.append({"source": "drive", "id": asset.pk, "path": asset.download_path, "issue": "mismatch"})
            continue
        ok += 1

    for msg in GmailMessage.objects.filter(pk__in=gmail_ids):
        if not os.path.exists(msg.raw_path):
            missing += 1
            details.append({"source": "gmail", "id": msg.pk, "path": msg.raw_path, "issue": "missing"})
            continue
        if msg.sha256 and _hash_file(msg.raw_path, "sha256") != msg.sha256:
            mismatched += 1
            details.append({"source": "gmail", "id": msg.pk, "path": msg.raw_path, "issue": "mismatch"})
            continue
        ok += 1

    sampled = len(drive_ids) + len(gmail_ids)
    run = IntegrityRun.objects.create(
        finished_at=timezone.now(),
        sampled=sampled, ok=ok, missing=missing, mismatched=mismatched,
        details=details,
    )
    if missing or mismatched:
        try:
            from core import notify
            notify.send(
                "integrity_problems_found",
                "Integrity check found problems",
                f"{missing} missing, {mismatched} mismatched out of {sampled} sampled (run #{run.pk}).",
            )
        except Exception:
            pass
    return {"integrity_run_id": run.pk, "sampled": sampled, "ok": ok, "missing": missing, "mismatched": mismatched}


@shared_task(name="core.tasks.task_run_export")
def task_run_export(job_id):
    """Phase 36 -- build a large export archive on disk (MEDIA_ROOT/exports/)
    and mark the ExportJob DONE/ERROR. Read-only on the source files it copies
    from; only ever writes its own archive file + the ExportJob row.
    """
    import uuid

    from django.conf import settings
    from django.utils import timezone

    from core.export import write_archive_to_file
    from core.models import ExportJob

    job = ExportJob.objects.get(pk=job_id)
    job.status = ExportJob.Status.RUNNING
    job.save(update_fields=["status"])

    try:
        gmail_ids = (job.item_ids or {}).get("gmail") or []
        media_ids = (job.item_ids or {}).get("media") or []
        from core.export import resolve_export_items
        items = resolve_export_items("selection", gmail_ids=gmail_ids, media_ids=media_ids)

        exports_dir = os.path.join(settings.MEDIA_ROOT, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        ext = "zip" if job.format == "zip" else "tar.gz"
        dest_path = os.path.join(exports_dir, f"export-{job.id}-{uuid.uuid4().hex[:8]}.{ext}")

        write_archive_to_file(items, job.format, dest_path)

        job.file_path = dest_path
        job.status = ExportJob.Status.DONE
        job.finished_at = timezone.now()
        job.save(update_fields=["file_path", "status", "finished_at"])
    except Exception as exc:
        job.status = ExportJob.Status.ERROR
        job.error = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
    return {"job_id": job.id, "status": job.status}


@shared_task(name="core.tasks.task_restore_smoke_test")
def task_restore_smoke_test():
    """Phase 37 — "Can I restore a file?": pick one random VERIFIED item,
    restore it into a throwaway subfolder of RESTORE_ROOT, re-hash the
    restored copy against the source file, record pass/fail in the Phase 31
    IntegrityRun table, then delete the throwaway copy. Read-only on the
    source; the only writes are the temporary restored file (removed before
    returning) and the IntegrityRun row.
    """
    import shutil
    import uuid

    from django.utils import timezone

    from core.export import resolve_export_items
    from core.models import IntegrityRun
    from core.restore import sha256_file, resolve_dest_root, restore_items
    from core.verification import DRIVE_BACKED_UP_STATES, GMAIL_BACKED_UP_STATES
    from google_gmail_backup.models import GmailMessage
    from google_media_backup.models import DriveAsset

    candidates = []
    gmail_id = _sample_ids(GmailMessage.objects.filter(state__in=GMAIL_BACKED_UP_STATES).exclude(raw_path=""), 1)
    drive_id = _sample_ids(DriveAsset.objects.filter(state__in=DRIVE_BACKED_UP_STATES).exclude(download_path=""), 1)
    candidates = [("gmail", gmail_id[0]) if gmail_id else None, ("media", drive_id[0]) if drive_id else None]
    candidates = [c for c in candidates if c]

    if not candidates:
        run = IntegrityRun.objects.create(finished_at=timezone.now(), sampled=0)
        return {"integrity_run_id": run.pk, "sampled": 0, "reason": "no backed-up items to sample"}

    kind, db_id = random.choice(candidates)
    kwargs = {"gmail_ids": [db_id]} if kind == "gmail" else {"media_ids": [db_id]}
    items = resolve_export_items("selection", **kwargs)

    subdir = f"_smoke_test/{uuid.uuid4().hex[:12]}"
    ok = missing = mismatched = 0
    details = []

    if not items:
        missing += 1
        details.append({"source": kind, "id": db_id, "path": "", "issue": "missing"})
    else:
        item = items[0]
        source_sha = sha256_file(item["disk_path"])
        result = restore_items(items, dest_subdir=subdir, on_conflict="overwrite")[0]
        restored_sha = sha256_file(result["dest_path"])
        if restored_sha == source_sha:
            ok += 1
        else:
            mismatched += 1
            details.append({"source": kind, "id": db_id, "path": item["disk_path"], "issue": "mismatch"})
        shutil.rmtree(resolve_dest_root(subdir), ignore_errors=True)

    run = IntegrityRun.objects.create(
        finished_at=timezone.now(), sampled=1, ok=ok, missing=missing, mismatched=mismatched, details=details,
    )
    return {"integrity_run_id": run.pk, "sampled": 1, "ok": ok, "missing": missing, "mismatched": mismatched}


DUMP_GLOB_PREFIX = "backdeezup-"
DUMP_SUFFIX = ".dump"


def prune_old_dumps(directory, keep_last):
    """Deletes every ``backdeezup-*.dump`` file in ``directory`` except the
    ``keep_last`` most recently modified ones. Returns the list of deleted paths.
    Pure filesystem logic -- no Postgres connection, so it's fully unit-testable
    and shared between the Beat task and any future manual pruning."""
    if not os.path.isdir(directory):
        return []
    dumps = [
        os.path.join(directory, name) for name in os.listdir(directory)
        if name.startswith(DUMP_GLOB_PREFIX) and name.endswith(DUMP_SUFFIX)
    ]
    dumps.sort(key=os.path.getmtime, reverse=True)
    to_delete = dumps[max(keep_last, 0):]
    for path in to_delete:
        os.remove(path)
    return to_delete


@shared_task(name="core.tasks.task_db_backup")
def task_db_backup():
    """Phase 38 — optional weekly dump + prune. Off unless DB_BACKUP_ENABLED.
    Independent of `make db-backup` (which execs pg_dump inside the `db`
    container from the host) -- this runs pg_dump from inside the celery
    container against DATABASE_URL, into the same bind-mounted directory, so
    both paths prune each other's dumps consistently.
    """
    import subprocess
    from datetime import datetime

    from django.conf import settings

    if not settings.DB_BACKUP_ENABLED:
        return {"skipped": True, "reason": "DB_BACKUP_ENABLED is False"}

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        return {"skipped": True, "reason": "DATABASE_URL not set"}

    out_dir = settings.DB_BACKUP_DIR
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(out_dir, f"{DUMP_GLOB_PREFIX}{ts}{DUMP_SUFFIX}")

    subprocess.run(["pg_dump", "-Fc", "-f", dest, "--dbname", database_url], check=True)
    deleted = prune_old_dumps(out_dir, settings.DB_BACKUP_KEEP_LAST)
    return {"file": dest, "pruned": deleted}


@shared_task(name="core.tasks.task_check_backup_freshness")
def task_check_backup_freshness():
    """Phase 33 -- new Beat check: notify if no successful RunLog finished in the
    last NOTIFY_STALE_BACKUP_HOURS hours. Read-only; disabled when the setting is 0.
    """
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone

    from core import notify
    from google_media_backup.models import RunLog

    hours = settings.NOTIFY_STALE_BACKUP_HOURS
    if not hours:
        return {"checked": False, "reason": "disabled"}

    cutoff = timezone.now() - timedelta(hours=hours)
    last_ok = RunLog.objects.filter(status="OK", finished_at__gte=cutoff).exists()
    if not last_ok:
        notify.send(
            "no_successful_backup",
            "No successful backup recently",
            f"No RunLog finished with status OK in the last {hours}h.",
        )
    return {"checked": True, "stale": not last_ok, "hours": hours}
