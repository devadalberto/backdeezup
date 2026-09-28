# Operations Manual

Day-to-day operations guide. Everything here can be run by a human with `make` commands — no AI, no Django knowledge required.

---

## Daily Operations (Celery handles automatically)

Only these three run on schedule via Celery Beat (`backend_django/celery_app.py` is
the source of truth — everything else below needs a manual command or a dashboard
button):

| Task | Schedule | Manual command |
|------|----------|----------------|
| Gmail incremental sync | Every 6h | `make gmail-incremental` |
| Apply protected senders | Every 6h (offset 30m) | (runs with sync) |
| Cleanup rules (all enabled) | 3x/day (06/12/18 UTC) | `make cleanup-run` |

**Not automatic today** (run manually, or via the dashboard's action buttons —
`/dashboard/`): Drive/Photos/Documents discovery and download, Gmail reconciliation,
soft-delete purge. See the command list below.

---

## Gmail Pipeline

### Discover new messages
```bash
make gmail-discover
```
Finds all message IDs in Gmail (50 pages x 500). Safe to re-run — idempotent.

### Download messages
```bash
make gmail-loop LIMIT=500 WORKERS=10
```
Downloads `.eml` files for all DISCOVERED messages. Concurrent (10 workers default).

### Verify backups
```bash
make gmail-verify
```
Confirms `.eml` files exist on disk for DOWNLOADED messages.

### Check progress
Visit `/admin/gmail/dashboard/` or:
```bash
make gmail-progress
```

### Reconcile (sync DB with Gmail reality)
```bash
make gmail-reconcile
```
Checks all VERIFIED messages against live Gmail. Marks missing as SOFT_DELETED.

---

## Gmail Cleanup

### Run all rules (real execution)
Visit `/admin/gmail/ops/` → "Execute All Enabled Rules"

### Empty Gmail trash
Visit `/admin/gmail/ops/` → "Empty Trash"

Or via CLI:
```bash
make gmail-empty-trash-dry   # count first
make gmail-empty-trash       # permanently delete
```

### Manage rules
- View/edit: `/admin/google_gmail_backup/cleanuprule/`
- Rule builder: `/admin/gmail/rule-builder/`
- Seed defaults: `make seed-rules` (15 rules) + `make seed-inbox-rules` (12 rules)

---

## Drive / Photos Pipeline

### Discover documents
```bash
make docs-discover    # PDFs, Office, Google native formats
make discover         # images/videos from Drive
make photos-discover  # Google Photos items
```

### Download
```bash
make docs-download LIMIT=100    # documents (exports Google Docs → PDF)
make photos-download LIMIT=100  # Google Photos items
```

### Full pipeline (discover → download → verify → import)
```bash
make docs-run LIMIT=500
make photos-run LIMIT=500
```

### Check progress
```bash
make docs-progress
make photos-progress
make progress           # Drive/Photos pipeline stats (media only, not Gmail)
```

### Delete from Google (after backup verified)
```bash
make photos-delete LIMIT=100    # trash Photos from Google
```

---

## Media Vault (Wagtail)

### Import backed-up files into Wagtail
```bash
make import-media                    # all sources
make import-media ARGS="--source drive"
make import-media ARGS="--source gmail"
make import-media ARGS="--dry-run"   # preview only
```

### Browse media
- Gallery: `/vault/gallery/`
- Triage (keep/delete/skip): `/vault/review/`
- Documents: `/documents/<id>/`
- CMS: `/cms/`
- Admin: `/admin/wagtaildocs/` (documents), `/admin/wagtailimages/` (images)

---

## Stack Management

### Start / Stop
```bash
make up        # start all 6 containers
make down      # stop all
make restart   # down + up
make ps        # show status
make logs      # tail all logs
```

### Upgrade (pull latest code + redeploy)
```bash
make redeploy  # git pull + build + restart + migrate
```
Full walkthrough (backup-first, the non-root `fix-perms` one-timer, rolling back,
diffing new `.env` variables): `docs/upgrading.md`.

### Celery
```bash
make celery-status   # check workers
make celery-logs     # tail worker + beat logs
```

---

## Sizing for Bigger Hardware

Gmail downloads are I/O-bound (network call + `.eml` write + SHA-256 hash + DB
save per message) — more vCPUs mostly help by letting more of these run in
parallel without contending for cores, not by making each one faster. The real
ceiling on `make gmail-loop WORKERS=N` is Gmail's own per-user API quota, not
your CPU count — pushing far past ~15-20 workers tends to trade throughput for
429 rate-limit errors rather than gain anything. `CELERY_CONCURRENCY` is a
separate knob: it governs how many *Celery tasks* (reconcile, verify, media
backup) run in parallel, not the threads inside one gmail-loop batch.

All values below are `.env` vars (Phase 53) with defaults matching the
project's original hardcoded ones — unset, nothing changes.

| Hardware       | `WORKERS` (gmail-loop) | `CELERY_CONCURRENCY` | `CELERY_CPUS` / `CELERY_MEMORY` | `MAX_CONCURRENT_DOWNLOADS` |
|----------------|------------------------|-----------------------|----------------------------------|------------------------------|
| 2 vCPU / 4GB   | 10 (default)           | 2 (default)           | 2.0 / 1G (default)               | 2 (default)                  |
| 4 vCPU / 8GB   | 12–15                  | 3                     | 3.0 / 2G                         | 3                             |
| 12 vCPU / 36GB | 16–20                  | 4                     | 4.0 / 4G                         | 4                             |

Only raise `GOOGLE_API_MAX_RPS` (default `0`, disabled) if you actually see
429/`rateLimitExceeded` errors climbing in `make celery-logs` — don't
preemptively throttle. After changing any `.env` value: `make up` (not
`restart` — see the Troubleshooting table below for why).

---

## Database Backup / Restore

### Back up
```bash
make db-backup
```
Runs `pg_dump -Fc` inside the `db` container and writes a timestamped custom-format
dump to `./backups/backdeezup-<timestamp>.dump` on the host (gitignored). Safe to
run anytime — it only reads the database.

### Restore
```bash
make db-restore FILE=backups/backdeezup-20260101-000000.dump
```
Asks for a typed `yes` confirmation, then runs `pg_restore --clean --if-exists`
inside the `db` container against the **currently running** database — this
drops and recreates every object the dump contains. Refuses to run without
`FILE=` or if that file doesn't exist. There is no separate "restore into a
throwaway DB" target: point a *second*, disposable Postgres instance's
`DATABASE_URL` at the dump instead if you want to inspect it without touching
the live database (see "Tested restore" below).

### Optional weekly auto-backup + pruning
Off by default. Set in `.env`:
```bash
DB_BACKUP_ENABLED=1        # turns on the weekly Beat task (Sun 04:00 UTC)
DB_BACKUP_KEEP_LAST=14     # dumps kept before older ones are pruned
```
This runs `pg_dump` from inside the `celery` worker container (against
`DATABASE_URL`, into the same `./backups/` bind mount `make db-backup` uses) and
then deletes everything past the newest `DB_BACKUP_KEEP_LAST` dumps. It shares
the exact naming scheme (`backdeezup-<timestamp>.dump`) and directory with
`make db-backup`, so manual and automatic dumps are pruned together as one set.
This flag does not affect `make db-backup` / `make db-restore`, which always work.

### Tested restore (do this at least once per install)
1. `make db-backup` to produce a fresh dump.
2. Spin up a throwaway Postgres container against a scratch database, e.g.:
   ```bash
   docker run --rm -d --name backdeezup-restore-test \
     -e POSTGRES_PASSWORD=scratch -e POSTGRES_DB=scratch postgres:16
   docker exec -i backdeezup-restore-test pg_restore -U postgres -d scratch \
     < backups/backdeezup-<timestamp>.dump
   ```
3. Compare row counts against the live database for a few key tables, e.g.:
   ```bash
   docker exec -i backdeezup-restore-test psql -U postgres -d scratch -c \
     "select count(*) from google_gmail_backup_gmailmessage;"
   docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
     "select count(*) from google_gmail_backup_gmailmessage;"'
   ```
   Counts should match. `docker rm -f backdeezup-restore-test` when done.

This only covers the database. `MEDIA_ROOT` has no built-in backup command — see
`docs/disaster-recovery.md` for what that means if you lose it, the database, or
both, and how far you can get back.

---

## Troubleshooting

| Symptom | Check | Fix |
|---|---|---|
| Stack won't start | `docker compose ps` | `make up` |
| Gmail 403 / token expired | Logs show `invalid_grant` | `rm secrets/google_token.json && make auth` |
| Rules execute with 0 affected | Audit log shows DRY_RUN or empty query | Check rule's `gmail_query` in admin |
| Celery not running | `make celery-status` | `docker compose restart celery celerybeat` |
| CSRF 403 on login | New hostname not in .env | Add to `CSRF_TRUSTED_ORIGINS` in `.env`, then `make up` |
| Progress bar "Loading..." | HTMX not loaded | `Ctrl+Shift+R` (hard refresh) |
| `docker compose restart` didn't pick up .env change | restart reuses old env | Always `make up` (not restart) after .env edits |
| `gmail-loop` shows 0 downloaded, errors climbing every pass | `docker compose exec web python manage.py shell -c "from google_gmail_backup.models import GmailMessage; print(GmailMessage.objects.exclude(error='').values_list('error', flat=True).first())"` | If the error is a 404/`notFound`: self-resolving since Phase 51 (a confirmed-gone message is marked `SOFT_DELETED` instead of blocking the queue forever) — just retry. Any other error: investigate that message specifically, it's still just being retried |

---

## Scheduled Tasks (Celery Beat)

Source of truth: `backend_django/celery_app.py`. The static entries get seeded into
`/admin/django_celery_beat/` as `PeriodicTask` rows on first Beat startup, and can be
edited there afterward (the setup wizard's Schedule step re-points the same three rows
to a daily/weekly preset — it doesn't add new ones):

| Task | Frequency | On by default? |
|------|-----------|-----------------|
| `task_gmail_incremental_sync` | Every 6 hours | Yes |
| `task_apply_protected_senders` | Every 6 hours (offset 30m) | Yes |
| `task_run_cleanup_rules` | 3x/day (06:00, 12:00, 18:00 UTC) | Yes |
| `task_integrity_check` (Phase 31) | Weekly Monday 03:00 UTC | Yes (`INTEGRITY_CHECK_ENABLED`) |
| `task_check_backup_freshness` (Phase 33) | Hourly | No (`NOTIFY_STALE_BACKUP_HOURS=0`) |
| `task_restore_smoke_test` (Phase 37) | Weekly Monday 04:30 UTC | No (`RESTORE_SMOKE_TEST_ENABLED=0`) |
| `task_db_backup` (Phase 38) | Weekly Sunday 04:00 UTC | No (`DB_BACKUP_ENABLED=0`) |

**Not scheduled at all today** — always manual (`make ...` or a dashboard button):
Drive/Photos/Documents discovery and download, Gmail reconciliation
(`task_gmail_reconcile`), soft-delete purge (`task_purge_expired_soft_deletes`).

---

## Make Targets Reference

Run `make help` for the full list. Key targets:

```bash
# Pre-flight
make preflight              # check all prerequisites

# Gmail
make gmail-discover         # discover message IDs
make gmail-loop             # download + verify loop
make gmail-reconcile        # sync DB with Gmail reality
make gmail-purge-expired    # purge 90d+ soft-deletes

# Drive / Photos
make docs-run               # full documents pipeline
make photos-run             # full photos pipeline
make import-media           # import to Wagtail vault

# Testing
make test                   # unit + smoke (fast, <2s)
make test-full              # lint + unit + integration
make test-cov               # coverage report

# Maintenance
make redeploy               # upgrade from git
make celery-status          # check workers
```
