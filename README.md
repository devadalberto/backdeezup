# BackDeezUp

> Self-hosted Google Drive, Gmail & Photos backup. Because cloud storage isn't a backup, it's a subscription to anxiety.

[![CI](https://github.com/devadalberto/backdeezup/actions/workflows/ci.yml/badge.svg)](https://github.com/devadalberto/backdeezup/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-6.0%2B-green)](https://www.djangoproject.com/)
[![Celery](https://img.shields.io/badge/celery-5.x-brightgreen)](https://docs.celeryq.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://devadalberto.github.io/backdeezup)

In a hurry and already comfortable with Docker/Django/OAuth? Skip straight to the
[dev quickstart](docs/dev-quickstart.md) — a terse command list, no explanation.
This README walks through the same ground step by step.

---

## What this actually does (read this first)

**Backed up today:**

| Source | What | How |
|---|---|---|
| Gmail | Every message, as a raw `.eml` file | Gmail API |
| Google Drive | Media (images/videos matching `GOOGLE_MIME_ALLOWLIST` — defaults to `image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/x-msvideo`) | Drive API |
| Google Drive | Documents (PDF, Office formats, Google Docs/Sheets/Slides — exported to PDF/xlsx/csv) | Drive API |
| Google Photos | Photos and videos | Drive API (Google blocks the Photos Library API for unverified apps, so Photos items are fetched as Drive file IDs instead) |

**Not backed up:** Calendar, Contacts, Tasks, Keep, or any other Google Workspace
data — nothing in this codebase talks to those APIs. Drive media outside the mime
allowlist above is skipped by the media pipeline (documents are covered by the
separate documents pipeline).

**One Google account at a time.** There's no multi-account UI yet — connecting a
second account isn't supported today. It's planned (see `docs/ai-dev/GOALS_TODOS.md`,
phases 14/16-20), but don't rely on it existing.

**Backup, not sync, not archive, not cleanup — these are different things:**

- **Backup** (what this is): copies each item once. If you edit or delete the
  original in Google afterward, the local copy is unaffected.
- **Sync** (what this is *not*): the local copy is not kept in lockstep with
  live edits. Discovery finds *new* items; it doesn't re-check or re-download
  content for items already marked downloaded.
- **Archive** (partial, on demand): the export feature (see "Restore" below)
  bundles already-verified items into a portable ZIP/TAR — you trigger that
  yourself, it's not automatic or versioned.
- **Cleanup** (separate, opt-in, Gmail-only): rule-based *deletion from Gmail*
  (not from your local backup), dry-run by default, with protected senders
  exempt. See "Cleanup" below. It is off until you turn it on.

---

## Supported platforms

| Platform | Status |
|---|---|
| Linux + Docker Engine/Compose | Runs in CI on every push (GitHub Actions, `ubuntu-latest`) |
| WSL2 (Debian 13) on Windows Server 2025 | Manually tested for production deployment — see `docs/deployment.md` |
| macOS + Docker Desktop | Should work (it's just Docker Compose) but not verified — no test run recorded |

Requires only Docker + Docker Compose v2 (the `docker compose` plugin, not the
standalone `docker-compose` binary). No local Python/uv/Node needed — everything
runs in containers.

**Hardware:** no benchmarked minimum exists yet. What's actually configured, in
`docker-compose.yml`'s per-container resource limits: `web` (1.0 CPU / 512MB), `celery`
(2.0 CPU / 1GB), `celerybeat` (0.25 CPU / 192MB) — a combined ceiling of about 3.25
CPU / 1.7GB for those three. `db`, `redis`, and `nginx` have no configured limit today.
Treat this as the compose file's configured ceiling, not a tested "runs comfortably
on X" claim.

---

## Install

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
cp .env.sample .env
```

Fill in at minimum (everything else in `.env.sample` has a working default):

```bash
# python3 -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET_KEY=<long random string>

# python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
GOOGLE_ENCRYPTION_KEY=<44-char Fernet key>
```

Then:

```bash
mkdir -p secrets
cp ~/Downloads/client_secret_*.json secrets/google_client.json   # Desktop app OAuth client, type "installed"

make gen-certs                                    # self-signed TLS for local HTTPS
make preflight                                    # sanity checks -- fix anything it flags
make build && make up && make migrate && make superuser
```

Once `make ps` shows all 6 containers up, open **`https://localhost:8445/setup/`**
(the setup wizard doesn't open itself — you go there) to create your admin account
and walk the rest of setup in a browser. Or skip the wizard entirely and use
`make superuser` (just ran above) plus the manual steps in the
[dev quickstart](docs/dev-quickstart.md) — the wizard is a convenience, not a
requirement.

**Don't want to clone the repo at all?** `scripts/install.sh` (Phase 49) sets up a
fresh install from the published image instead — see `docs/deployment.md` →
"One-line install".

---

## Connect Google

The wizard's Connect step runs the same OAuth flow as `make auth`: it opens Google's
consent screen, you approve access, and the encrypted token lands in
`secrets/google_token.json`. Only one account can be connected at a time (see above).

If your Drive OAuth client is missing scopes or gets revoked later, the dashboard
and health page surface it as "Google sign-in expired" / "Google access was revoked" —
reconnect from `/dashboard/connect/`.

---

## Choose what to back up

The wizard's Services step asks which of Gmail / Drive / Photos you use, with
checkboxes for each (all three checked by default). **Today this only scopes the
wizard's own one-time test backup** (the next step) — it isn't a persistent on/off
switch for the running pipelines. In practice: whichever of the three pipelines you
run (manually, or via a dashboard button) will back up going forward; there's no
config flag yet to permanently disable one.

---

## First backup

Either let the wizard's Test step run a small (10-item) backup automatically, or run
it yourself:

```bash
make seed-rules              # 15 cleanup rules, all disabled -- review before enabling any
make gmail-discover          # finds every message ID
make gmail-loop LIMIT=500    # downloads .eml files until the queue is empty
make docs-run                # Drive documents: discover -> download -> verify
make photos-run              # Google Photos: discover -> download -> verify
```

Or from the dashboard (`/dashboard/`): the **Gmail backup**, **Drive backup**, and
**Photos backup** buttons each enqueue the same discover-then-download chain as a
background job.

---

## Verify

An item only counts as "backed up" once it's **VERIFIED** — both the file on disk
and its checksum have been confirmed to match what was recorded. Check
`/dashboard/verification/` for a live count of backed-up vs. missing-on-disk items
per source, plus the result of the last integrity run.

A weekly background task (`task_integrity_check`, on by default) re-hashes a random
sample of already-verified files against their stored checksum (MD5 for Drive,
SHA-256 for Gmail) and flags anything missing or mismatched — it only reads; it
never changes an item's state. You can also click **"Verify files"** on the
dashboard to run it on demand.

---

## Browse

| URL | What |
|---|---|
| `/vault/gallery/` | Photos and videos, imported into the Wagtail media vault |
| `/vault/review/` | Keep/delete triage queue |
| `/documents/<id>/` | Read a backed-up document inline |
| `/cms/` | Wagtail CMS admin |
| `/admin/gmail/dashboard/` | Gmail backup progress |

Items need `make import-media` (or the dashboard's **"Import media"** button) to
appear in the vault — downloading and verifying is separate from importing.

---

## Restore

Two independent things live under this name:

- **Restore a backed-up file to a local directory**: Django admin's "Export
  selected" bulk action (on Gmail/Drive asset list pages), or `/dashboard/export/`,
  bundles verified items into a streamed ZIP or TAR/gzip (sha256 computed in the
  same pass, never buffered whole in memory). Restoring that bundle back onto disk
  writes only inside `RESTORE_ROOT` (path-traversal checked) and offers `skip`,
  `overwrite`, `rename`, or `compare`-by-checksum on a name collision.
- **"Can I actually restore a file?"**: the dashboard has a button by that name
  that restores one real, random VERIFIED item to a throwaway directory, compares
  its checksum, and deletes the throwaway copy — a live proof the backup is
  restorable, not just present.

Restoring *back into Google* (re-uploading a deleted Drive file, for example) isn't
built — this restores to a local directory only.

---

## Schedules

Only three things run automatically via Celery Beat, defined in
`backend_django/celery_app.py`:

| Task | When |
|---|---|
| Gmail incremental sync | Every 6 hours |
| Apply protected-sender rules | Every 6 hours |
| Run enabled cleanup rules | 3x/day (06:00, 12:00, 18:00 UTC) |

The setup wizard's Schedule step re-points those same three to a simpler
daily/weekly preset you choose, in your `TIME_ZONE`. Everything else — Drive
documents, Google Photos, Gmail reconciliation, soft-delete purge — is **manual
only** today: a `make ...` target or a dashboard button. A few more Celery Beat
entries exist but are off unless you opt in: a weekly integrity re-hash (on by
default), an hourly stale-backup notification check, a weekly restore smoke test,
and a weekly database dump — see `docs/operations.md` for the full table and their
env var switches.

---

## Cleanup

Gmail-only, and off by default in every sense that matters:

- Rules live at `/admin/google_gmail_backup/cleanuprule/`, or build one visually at
  `/admin/gmail/rule-builder/`. Seed the defaults with `make seed-rules` (15 rules,
  disabled) — review and enable only what you want.
- The dashboard's **Execute All Enabled Rules** button requires a dry run younger
  than 24 hours whose exact item count you confirm before it'll run for real
  (`CLEANUP_REQUIRE_DRY_RUN=1` by default). `CLEANUP_PAUSED=1` is a global kill
  switch for every real cleanup run.
- **Protected senders** are starred and labeled, and are skipped by any rule that
  respects protection — the deliberate exemption list nothing else touches.
- A trash run can be undone once (a per-run flag, not a time-boxed window) — check
  the Gmail ops console (`/admin/gmail/ops/`) for the undo action.

Cleanup deletes from **Gmail**, not from your local `.eml` backups.

---

## Upgrade

```bash
make upgrade    # Phase 49: backs up the DB, pulls, migrates, restarts, health-checks
```

`make upgrade` asks before it does anything disruptive and prints exact rollback
instructions if the health check fails afterward — it never rolls back on its own.
Or by hand: `make fix-perms` (only the first time you build/run a non-root image
on an existing install) → `git pull origin main` → `make build` → `make down` →
migrate **before** starting (`docker compose run --rm web python manage.py
migrate`) → `make up`. `make redeploy` does the pull-through-up part of that in
one command, in that same order. Since the image runs as a non-root user by
default, `make fix-perms` re-owns the `media`/`staticfiles` Docker volumes once,
the first time — skipping it is safe to attempt: the container refuses to start
with a clear message instead of a confusing crash if it can't write to
`MEDIA_ROOT`. Check `docs/deployment.md` for the non-root/root escape-hatch
details and the LAN-bind-address change (both from Phase 39/41). Full walkthrough,
including rolling back and diffing new `.env` variables: `docs/upgrading.md`.

---

## Back up BackDeezUp itself

BackDeezUp's own PostgreSQL database — every discovered/downloaded/verified item's
metadata, cleanup rules, audit logs, wizard state — is separate from the Google
backups it manages, and needs its own backup:

```bash
make db-backup                                   # pg_dump -> ./backups/backdeezup-<timestamp>.dump
make db-restore FILE=backups/backdeezup-...dump   # asks for confirmation, then restores
```

Optional weekly auto-backup + pruning: set `DB_BACKUP_ENABLED=1` and
`DB_BACKUP_KEEP_LAST=14` (or your own number) in `.env`. See `docs/operations.md`
for a "restore into a throwaway Postgres container, compare row counts" drill worth
running at least once per install.

`make db-backup` only covers the database — `MEDIA_ROOT` (the actual downloaded
files) has no built-in backup command and needs to be copied off-host separately.
See `docs/disaster-recovery.md` for what's and isn't recoverable if either one
(or both) is lost.

---

## Storage

The dashboard and health page show a live estimate of days of storage remaining —
labeled as an estimate because that's exactly what it is, computed from your own
data, never a hardcoded number:

```
avg_item_bytes      = mean of the last 500 non-zero DriveAsset.size_bytes
                       + the last 500 non-zero GmailMessage.size_estimate
avg_daily_growth    = (items downloaded in the trailing 30 days) x avg_item_bytes
                       / (days since the earliest of those runs)
days_remaining      = free_disk_bytes / avg_daily_growth
```

It shows `--` until there's enough download history to compute it. A storage guard
(on by default, `STORAGE_GUARD_ENABLED`) pauses new downloads at `STORAGE_PAUSE_PCT`
disk usage (default 95%) and warns at `STORAGE_WARN_PCT` (default 85%) — it refuses
to *start* a download task rather than aborting one partway through.

---

## Troubleshoot

| Symptom | Check | Fix |
|---|---|---|
| Stack won't start | `docker compose ps` | `make up` |
| Gmail 403 / token expired | Logs show `invalid_grant` | `rm secrets/google_token.json && make auth` |
| Rules execute with 0 affected | Audit log shows DRY_RUN or empty query | Check the rule's `gmail_query` in admin |
| Celery not running | `make celery-status` | `docker compose restart celery celerybeat` |
| CSRF 403 on login | New hostname not in `.env` | Add it to `CSRF_TRUSTED_ORIGINS`, then `make up` |
| Progress bar stuck at "Loading..." | HTMX not loaded | Hard refresh (Ctrl+Shift+R) |
| `.env` edit didn't take effect | `docker compose restart` reuses the old env | Always `make up`, never `restart`, after editing `.env` |
| Container refuses to start, permission error | Upgrading an existing install to the non-root image | `make fix-perms`, then `make up` |
| Any other error | `/health/` (staff-only) | Shows a human-readable title + hint, not a stack trace |

More detail, including a database disaster-recovery drill: `docs/operations.md` and
the [full docs site](https://devadalberto.github.io/backdeezup).

---

## License

MIT — do whatever you want, just don't blame me when Google changes their API again.
