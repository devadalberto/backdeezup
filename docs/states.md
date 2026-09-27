# State Machine

Every `DriveAsset` row moves through exactly six states. No state can be skipped, and only the designated endpoint advances each transition.

---

## State diagram

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED
    DISCOVERED --> DOWNLOADED
    DOWNLOADED --> IMPORTED
    IMPORTED --> VERIFIED
    VERIFIED --> DELETE_PENDING
    DELETE_PENDING --> DELETED

    DISCOVERED --> DISCOVERED : download error, retry
    DOWNLOADED --> DOWNLOADED : import error, retry
```

---

## State reference

### DISCOVERED

The asset has been found in Google Drive or Google Photos. Metadata is stored but no file has been downloaded yet.

**Set by:** `POST /sync/discover`, `/sync/discover-files`, `/sync/discover-photos`

**Stored:** `drive_id`, `name`, `mime_type`, `size_bytes`, `md5_checksum`, `discovered_at`

---

### DOWNLOADED

The binary file has been downloaded to local disk at `download_path`. The download is atomic — written to `<path>.part` first, then renamed.

**Set by:** `POST /sync/download`

**Stored:** `download_path`, `downloaded_at`

**Error handling:** If the download fails, `error` is recorded and the asset stays in `DISCOVERED` for retry.

---

### IMPORTED

The file has been SHA-256 hashed and copied into the media library at `media/imported/<sha[:2]>/<sha>.ext`. A `MediaItem` record has been created (or reused if the hash already exists — deduplication).

**Set by:** `POST /sync/import`

**Stored:** `media_item` FK, `imported_at`

---

### VERIFIED

Both proofs of local safety have been independently confirmed:

1. `os.path.exists(download_path)` — file exists on disk
2. `MediaItem.objects.filter(id=media_item_id).exists()` — DB record exists

**Set by:** `POST /sync/verify`

**Error handling:** If either proof fails the asset stays in `IMPORTED` and the error is recorded.

---

### DELETE_PENDING

The asset is queued for Drive deletion. The retention guard check has not yet been applied.

**Set by:** `POST /sync/mark-delete`

---

### DELETED

The file has been removed from Google Drive. The local copy remains intact.

**Set by:** `POST /sync/commit-delete`

**Conditions:**
- `(now - imported_at).days >= MIN_RETENTION_DAYS` must be true, or `force=true` must be passed
- Deletion mode is controlled by `DRIVE_DELETE_MODE` (`trash` or `hard`)

---

## Retention guard

The retention guard prevents premature deletion. By default an asset must be held locally for at least **3 days** from `imported_at` before `commit-delete` will act on it.

```
MIN_RETENTION_DAYS=3  # default, configurable in .env
```

Override per request with `?force=true` (use with caution).

---

## Deletion modes

| Mode | Behaviour | Recoverable |
|---|---|---|
| `trash` (default) | Moves file to Google Drive trash | Yes — 30 days |
| `hard` | Permanently deletes from Google Drive | No |

Set via `DRIVE_DELETE_MODE` in `.env`.

---

## Gmail Message States

Gmail messages go through a separate state machine:

DISCOVERED → DOWNLOADED → VERIFIED → TRASHED → SOFT_DELETED → DELETED

### State diagram

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED
    DISCOVERED --> DOWNLOADED
    DOWNLOADED --> VERIFIED
    VERIFIED --> TRASHED : cleanup rule
    VERIFIED --> SOFT_DELETED : user deleted in Gmail
    TRASHED --> DELETED : trash emptied
    SOFT_DELETED --> DELETED : 90-day retention purge
```

### State reference

| State | Meaning |
|-------|---------|
| DISCOVERED | Message ID found in Gmail, not yet downloaded |
| DOWNLOADED | .eml file saved to disk |
| VERIFIED | .eml file confirmed on disk with SHA-256 |
| TRASHED | Moved to Gmail trash by cleanup rule |
| SOFT_DELETED | Gone from Gmail (user deleted or trash emptied), .eml backup retained |
| DELETED | Purged from DB after 90-day retention period, metadata preserved in snapshot |

### Notes

- **SOFT_DELETED retention** — messages are kept for 90 days, then purged to DELETED
- **metadata_snapshot** — JSON field freezes subject/from/to/date/labels/size at deletion time
- **Restore-to-Gmail** — possible from SOFT_DELETED if .eml file still exists on disk

---

## Success definition — "backed up" (Phase 31)

An item counts as backed up only once it has been through `VERIFIED` — i.e. it
was downloaded, checksummed, and confirmed to still exist on disk. A state
that comes *after* `VERIFIED` in either machine still counts, because it can
only be reached by having passed through `VERIFIED` first; those later states
describe what happened to the *source* copy (Drive/Gmail), not the local
backup.

- `DriveAsset` backed up: `VERIFIED`, `DELETE_PENDING`, `DELETED`
- `GmailMessage` backed up: `VERIFIED`, `TRASHED`, `SOFT_DELETED`, `DELETED`

In code this is `core.verification.DRIVE_BACKED_UP_STATES` /
`GMAIL_BACKED_UP_STATES` — the single source of truth the dashboard and the
`/dashboard/verification/` report both read from. `DISCOVERED`, `DOWNLOADED`
and (Drive-only) `IMPORTED` never count, even though a file may already sit on
disk at those states — it hasn't been checksum-confirmed yet.

The `/dashboard/verification/` report additionally shows, per source: items
whose stored path no longer exists on disk (a live check, one `os.path.exists`
per backed-up item), the oldest verified timestamp, and the result of the
latest scheduled integrity check. That check (`core.tasks.task_integrity_check`,
weekly via Celery Beat, gated by `INTEGRITY_CHECK_ENABLED`, default on) samples
`INTEGRITY_CHECK_SAMPLE_SIZE` (default 200) backed-up items, re-hashes the file
on disk (MD5 for Drive assets, SHA-256 for Gmail messages — matching whichever
checksum each model already stores) and compares it to the stored value. It
only reads files and writes its own `IntegrityRun` row; it never changes
`state` on the item it checked.
