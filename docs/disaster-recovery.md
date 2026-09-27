# Disaster Recovery

This is the "something is actually gone" playbook. For routine operations (day-to-day
backup/cleanup, the `db-backup`/`db-restore` reference, the tested-restore drill) see
`docs/operations.md`. This page is about the failure cases, and what you can and
cannot recover from with what BackDeezUp gives you today.

---

## What you need *before* disaster strikes

BackDeezUp has two things worth losing, and only one of them has a built-in backup command:

| What | Backed up by | Off-host by default? |
|---|---|---|
| PostgreSQL database (item state, cleanup rules, audit logs, wizard state) | `make db-backup` → `./backups/*.dump` | **No** — writes to the host running Docker. Copy `./backups/` and `MEDIA_ROOT` somewhere else (another disk, another machine, cloud storage) yourself. |
| `MEDIA_ROOT` (the actual downloaded `.eml`/images/videos/documents) | Nothing. There is no `make media-backup`. | No. |

`docs/index.md`'s FAQ answer ("back up the Docker `media/` volume and the PostgreSQL
data directory") is the whole story — BackDeezUp does not copy either of them off the
host for you. If the host itself is destroyed and neither was copied elsewhere first,
everything below is moot.

---

## Scenario: lost the whole server (disk died, host destroyed)

Recoverable only if you copied `./backups/*.dump` **and** `MEDIA_ROOT` off-host beforehand.

1. Provision a new host, clone the repo, `cp .env.sample .env` and fill it in with
   the **same** `GOOGLE_ENCRYPTION_KEY` and `DJANGO_SECRET_KEY` you used before (a new
   `GOOGLE_ENCRYPTION_KEY` makes your restored token undecryptable).
2. Restore `MEDIA_ROOT`'s contents into the new host's `media` volume before first `make up`.
3. `make build && make up && make migrate`
4. Restore the database dump:
   ```bash
   make db-restore FILE=backups/backdeezup-<timestamp>.dump
   ```
5. `make auth` if the token wasn't restored with `MEDIA_ROOT`, or if it was and Google
   has since revoked it (check `/health/`).
6. Spot-check: `/dashboard/verification/` and the "Can I actually restore a file?"
   dashboard button.

If you only have the DB dump and not `MEDIA_ROOT`: the database will claim thousands of
items are `DOWNLOADED`/`VERIFIED` with `download_path`/`raw_path` values that no longer
exist. See the next scenario — you are effectively in it now, for everything.

---

## Scenario: lost `MEDIA_ROOT` only (database intact)

This is the scenario the current tooling handles worst, so read carefully.

The download tasks (`gmail-loop`, `docs-run`, `photos-run`, the dashboard action
buttons) only process items whose state is `DISCOVERED` — a normal rerun **will not**
re-download anything the database already marked `DOWNLOADED`/`IMPORTED`/`VERIFIED`,
even though the file on disk is gone. There is no built-in `repair`/`resync` management
command today. To force a re-download you have to reset the affected rows' state
yourself, in a Django shell:

```bash
make shell
```
```python
from google_media_backup.models import DriveAsset
DriveAsset.objects.filter(
    state__in=[DriveAsset.State.DOWNLOADED, DriveAsset.State.IMPORTED, DriveAsset.State.VERIFIED],
).update(state=DriveAsset.State.DISCOVERED, download_path="")

from google_gmail_backup.models import GmailMessage
GmailMessage.objects.filter(
    state__in=[GmailMessage.State.DOWNLOADED, GmailMessage.State.VERIFIED],
).update(state=GmailMessage.State.DISCOVERED, raw_path="")
```

Only run this if you're sure the files are actually gone (not just `MIN_RETENTION_DAYS`
before a scheduled Drive delete, for example) — it discards the "already downloaded"
signal for every row it touches, and if any of those Drive items were already deleted
from Google (cleanup ran, `DRIVE_DELETE_MODE=hard` or the trash window passed), **they
are gone for good**, database update or not. `task_integrity_check` (Phase 31) samples
existing backups and will report `missing` for files gone from disk without you having
to guess which rows are affected — check its output (`/dashboard/verification/`) before
running the reset above, to scope it to the actually-affected rows instead of resetting
everything.

Once reset, rerun the normal pipeline (`make gmail-loop`, `make docs-run`, `make
photos-run`) to re-download from Google.

---

## Scenario: lost the database only (files intact)

The better-covered case: `docs/index.md`'s FAQ is accurate here — "a re-run will
re-discover and re-verify everything." Discovery re-creates rows from Google's own
listing; verification re-hashes files already on disk. You lose custom cleanup rules,
audit logs, and wizard state (none of that is derivable from the files), so restore
from `make db-backup` first if you have a dump — only fall back to full rediscovery if
you don't.

---

## Scenario: OAuth token lost, corrupted, or revoked

Not really a disaster — this is designed to be recoverable:
```bash
rm secrets/google_token.json && make auth
```
Nothing already downloaded is affected. See `docs/authentication.md`.

---

## Scenario: your Google account itself is locked, hacked, or deleted

This is the whole reason BackDeezUp exists (see `README.md`'s opening). Everything
already downloaded and verified before that happened is safe in `MEDIA_ROOT` and the
database, independent of the Google account's fate. Nothing *not yet* downloaded at
that point is recoverable — this is why "First backup" (`README.md`) and the freshness
checks (`docs/operations.md`, `NOTIFY_STALE_BACKUP_HOURS`) matter: a backup tool that
hasn't run recently isn't protecting you from this scenario yet.

---

## What's explicitly not covered

- Restoring a file **back into** Google Drive or Gmail — not built (`docs/ai-dev/GOALS.md`
  Phase 14, backlog).
- Point-in-time DB recovery finer than your last `make db-backup` / weekly auto-backup —
  there's no WAL archiving here, just periodic `pg_dump`.
- Automated off-host replication of `MEDIA_ROOT` or `./backups/` — both are your
  responsibility today; see the table at the top of this page.
