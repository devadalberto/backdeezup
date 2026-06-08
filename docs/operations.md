# Operations Manual

Day-to-day operations guide. Everything here can be run by a human with `make` commands — no AI, no Django knowledge required.

---

## Daily Operations (Celery handles automatically)

These run on schedule via Celery Beat. Manual trigger if needed:

| Task | Schedule | Manual command |
|------|----------|----------------|
| Gmail incremental sync | Every 6h | `make gmail-incremental` |
| Apply protected senders | Every 6h | (runs with sync) |
| Cleanup rules | 3x/day (06/12/18) | `make cleanup-run` |
| Gmail reconciliation | Daily 03:00 UTC | `make gmail-reconcile` |
| Soft-delete purge (90d) | Weekly Sun 04:00 | `make gmail-purge-expired` |

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
make progress           # overall Drive/Photos stats
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

### Celery
```bash
make celery-status   # check workers
make celery-logs     # tail worker + beat logs
```

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

---

## Scheduled Tasks (Celery Beat)

Edit schedules at `/admin/django_celery_beat/`. Current defaults:

| Task | Frequency |
|------|-----------|
| `task_gmail_incremental_sync` | Every 6 hours |
| `task_apply_protected_senders` | Every 6 hours |
| `task_run_cleanup_rules` | 3x/day (06:00, 12:00, 18:00) |
| `task_gmail_reconcile` | Daily 03:00 UTC |
| `task_purge_expired_soft_deletes` | Weekly Sunday 04:00 UTC |
| `task_docs_discover` | Weekly Monday 03:00 UTC |
| `task_docs_download_batch` | Nightly 02:30 UTC |
| `task_photos_download_batch` | Nightly 02:00 UTC |

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
