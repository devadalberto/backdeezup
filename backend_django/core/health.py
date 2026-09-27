"""System health checks (Phase 24). Read-only.

``run_checks()`` runs every check and returns a list of
``{"key", "label", "status", "detail"}`` dicts, status being ok / warn / fail.
One check raising never affects the others: each is wrapped and reported as
"fail" with a ``humanize_error`` message.
"""
import os
import shutil
import tempfile
from datetime import timedelta, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.utils import timezone

from core.errors import humanize_error

OK, WARN, FAIL = "ok", "warn", "fail"

QUEUE_NAME = "celery"
QUEUE_WARN_DEPTH = 1000
DISK_WARN_FREE_PCT = 10
DISK_FAIL_FREE_PCT = 2
BEAT_STALE_AFTER = timedelta(hours=24)
FAILED_WINDOW = timedelta(hours=24)
CELERY_PING_TIMEOUT = 2.0


def _r(status, detail):
    return status, detail


def _explain(exc):
    info = humanize_error(exc)
    return f"{info['title']} -- {info['hint']}"


def check_database():
    with connection.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return _r(OK, f"{connection.vendor} reachable")


def check_migrations():
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    pending = len(executor.migration_plan(executor.loader.graph.leaf_nodes()))
    if pending:
        return _r(WARN, f"{pending} unapplied migration(s) -- run manage.py migrate")
    return _r(OK, "all migrations applied")


def _redis_client():
    import redis

    return redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)


def check_redis():
    _redis_client().ping()
    return _r(OK, "PING ok")


def check_celery_worker():
    from celery_app import app

    replies = app.control.inspect(timeout=CELERY_PING_TIMEOUT).ping() or {}
    if not replies:
        return _r(FAIL, f"no worker replied within {CELERY_PING_TIMEOUT:g}s")
    return _r(OK, f"{len(replies)} worker(s) responding")


def check_beat():
    from django_celery_beat.models import PeriodicTask

    last = (
        PeriodicTask.objects.filter(enabled=True, last_run_at__isnull=False)
        .order_by("-last_run_at")
        .values_list("last_run_at", flat=True)
        .first()
    )
    if last is None:
        return _r(WARN, "unknown -- no periodic task has recorded a run yet")
    age = timezone.now() - last
    stamp = timezone.localtime(last).strftime("%Y-%m-%d %H:%M %Z")
    if age > BEAT_STALE_AFTER:
        return _r(WARN, f"last scheduled run {stamp} (over 24h ago)")
    return _r(OK, f"last scheduled run {stamp}")


def check_queue_depth():
    depth = _redis_client().llen(QUEUE_NAME)
    if depth > QUEUE_WARN_DEPTH:
        return _r(WARN, f"{depth} tasks waiting in '{QUEUE_NAME}'")
    return _r(OK, f"{depth} tasks waiting in '{QUEUE_NAME}'")


def check_failed_tasks():
    from django_celery_results.models import TaskResult
    from google_media_backup.models import RunLog

    since = timezone.now() - FAILED_WINDOW
    failed_tasks = TaskResult.objects.filter(status="FAILURE", date_done__gte=since).count()
    failed_runs = RunLog.objects.filter(started_at__gte=since, status__in=("FAILED", "ERROR")).count()
    if failed_tasks or failed_runs:
        return _r(WARN, f"last 24h: {failed_tasks} failed task(s), {failed_runs} failed run(s)")
    return _r(OK, "no failed tasks or runs in the last 24h")


def check_storage():
    usage = shutil.disk_usage(settings.MEDIA_ROOT)
    free_pct = usage.free / usage.total * 100 if usage.total else 0
    detail = f"{usage.free / 1024**3:.1f} GB free of {usage.total / 1024**3:.1f} GB ({free_pct:.0f}% free)"
    if free_pct < DISK_FAIL_FREE_PCT:
        return _r(FAIL, detail)
    if free_pct < DISK_WARN_FREE_PCT:
        return _r(WARN, detail)
    return _r(OK, detail)


def check_oauth():
    from google_media_backup import services_google as sg

    path = sg._token_path_for_email(None)
    if not os.path.exists(path):
        return _r(FAIL, "no Google token saved -- run `make auth` to connect the account")
    creds = sg._load_creds()
    if creds is None:
        return _r(FAIL, "token file exists but cannot be read -- check GOOGLE_ENCRYPTION_KEY or reconnect")
    if not creds.refresh_token:
        return _r(WARN, "token has no refresh token -- reconnect the account")
    if creds.expiry:
        expiry = timezone.make_aware(creds.expiry, dt_timezone.utc) if timezone.is_naive(creds.expiry) else creds.expiry
        stamp = timezone.localtime(expiry).strftime("%Y-%m-%d %H:%M %Z")
        state = "expired, refreshes automatically" if creds.expired else "valid"
        return _r(OK, f"token present, access token {state} (expiry {stamp})")
    return _r(OK, "token present")


def check_version():
    path = Path(settings.BASE_DIR).parent / "VERSION"
    if not path.is_file():
        return _r(WARN, "VERSION file not found")
    return _r(OK, path.read_text().strip())


def check_media_write():
    root = settings.MEDIA_ROOT
    os.makedirs(root, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".health-")
    os.close(fd)
    os.unlink(tmp)
    return _r(OK, f"created and removed a temp file in {root}")


CHECKS = [
    ("database", "Database", check_database),
    ("migrations", "Migrations", check_migrations),
    ("redis", "Redis", check_redis),
    ("celery_worker", "Celery worker", check_celery_worker),
    ("beat", "Celery beat", check_beat),
    ("queue_depth", "Queue depth", check_queue_depth),
    ("failed_tasks", "Failed tasks (24h)", check_failed_tasks),
    ("storage", "Storage", check_storage),
    ("oauth", "Google OAuth token", check_oauth),
    ("version", "App version", check_version),
    ("media_write", "Media write test", check_media_write),
]


def run_checks():
    results = []
    for key, label, fn in CHECKS:
        try:
            status, detail = fn()
        except Exception as exc:  # a broken check must never break the page
            status, detail = FAIL, _explain(exc)
        results.append({"key": key, "label": label, "status": status, "detail": detail})
    return results


def overall_status(results):
    statuses = {r["status"] for r in results}
    if FAIL in statuses:
        return FAIL
    if WARN in statuses:
        return WARN
    return OK
