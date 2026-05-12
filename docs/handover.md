# Handover & Architecture

Last updated: 2026-05-12

## What this system does

**backdeezup** is a backend-first pipeline that safely migrates media from Google Drive / Google Photos into local Django-managed storage, then deletes the originals from Drive only after two independent proofs of local safety are confirmed.

**Two proofs required before any Drive delete:**

1. Local file exists at `download_path` on disk
2. A `MediaItem` row exists in the database (keyed by SHA-256)

---

## System overview

```mermaid
flowchart LR
    GD[(Google Drive\n/ Photos)]
    API[Django-Ninja\nAPI :8844/api]
    DB[(Database\nDriveAsset · MediaItem · RunLog)]
    FS[Local Storage\nmedia/imported/]
    AD[Django Admin\n:8844/admin\n+ Ops Console]

    GD -->|OAuth + Drive v3\nPhotos Library API| API
    API -->|state transitions| DB
    API -->|binary download + SHA-256 copy| FS
    AD -->|manage & monitor| DB
```

---

## Pipeline state machine

Each `DriveAsset` row moves through exactly these states. No state can be skipped.

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED : /sync/discover\n/sync/discover-files\n/sync/discover-photos

    DISCOVERED --> DOWNLOADED : /sync/download\n(Drive binary → local .part → renamed)

    DOWNLOADED --> IMPORTED : /sync/import\n(SHA-256 computed\ncopy to media/imported/\nMediaItem created)

    IMPORTED --> VERIFIED : /sync/verify\n(proof 1: file on disk ✓\nproof 2: MediaItem in DB ✓)

    VERIFIED --> DELETE_PENDING : /sync/mark-delete

    DELETE_PENDING --> DELETED : /sync/commit-delete\n(only if age ≥ MIN_RETENTION_DAYS)\n(trash or hard delete)

    DISCOVERED --> DISCOVERED : download error → retry
    DOWNLOADED --> DOWNLOADED : import error → retry
```

---

## Data model

```mermaid
erDiagram
    DriveAsset {
        string   drive_id       PK  "Google Drive ID (or photos:<id>)"
        string   name
        string   mime_type
        bigint   size_bytes
        string   md5_checksum
        string   download_path       "absolute path on disk"
        string   state               "DISCOVERED…DELETED"
        text     error               "last error message"
        int      media_item_id   FK
        datetime discovered_at
        datetime downloaded_at
        datetime imported_at
        datetime last_attempt_at
    }
    MediaItem {
        int      id         PK
        string   sha256     "unique — dedup key"
        file     file       "media/imported/<sha[:2]>/<sha>.ext"
        datetime created_at
    }
    RunLog {
        string   run_id     PK  "UUID per API call"
        string   status         "RUNNING | OK | ERROR"
        json     totals
        json     error_log
        datetime started_at
        datetime finished_at
    }
    DriveAsset }o--|| MediaItem : "SET NULL on delete"
```

---

## Full request/response sequence

```mermaid
sequenceDiagram
    participant C as Operator / Client
    participant A as Django-Ninja API
    participant G as Google API
    participant DB as Database
    participant FS as File System

    C->>A: POST /auth/connect
    A->>G: InstalledAppFlow OAuth (browser popup)
    G-->>A: credentials
    A->>FS: Fernet-encrypt → secrets/google_token.json
    A-->>C: "OAuth completed and token saved"

    note over C,A: Repeat discover → delete for each batch

    C->>A: POST /sync/discover[|-files|-photos]
    A->>G: Drive files().list / Photos mediaItems().list
    G-->>A: files[] + nextPageToken
    A->>DB: DriveAsset.get_or_create → state=DISCOVERED
    A-->>C: {discovered: N, run_id: uuid}

    C->>A: POST /sync/download?limit=20
    A->>G: files().get_media(fileId)
    G-->>A: binary stream
    A->>FS: write <path>.part → os.replace → <path>
    A->>DB: state=DOWNLOADED, download_path set
    A-->>C: {downloaded: N}

    C->>A: POST /sync/import?limit=20
    A->>FS: sha256_file(download_path)
    A->>FS: copy_into_media() → media/imported/<sha[:2]>/<sha>.ext
    A->>DB: MediaItem.get_or_create(sha256=digest)
    A->>DB: DriveAsset.media_item=FK, state=IMPORTED
    A-->>C: {imported: N}

    C->>A: POST /sync/verify?limit=50
    A->>FS: os.path.exists(download_path) → proof 1
    A->>DB: MediaItem.objects.filter(id=media_item_id).exists() → proof 2
    A->>DB: state=VERIFIED (both pass) or error (any fail)
    A-->>C: {verified: N}

    C->>A: POST /sync/mark-delete?limit=100
    A->>DB: VERIFIED → DELETE_PENDING (bulk update)
    A-->>C: {queued_for_delete: N}

    C->>A: POST /sync/commit-delete?force=false&limit=50
    A->>DB: check (now - imported_at).days >= MIN_RETENTION_DAYS
    A->>G: files().update(trashed=True) OR files().delete()
    A->>DB: state=DELETED
    A-->>C: {deleted: N, mode: trash|hard}
```

---

## Deployment topology

```mermaid
flowchart TD
    Browser -->|:8844| Nginx
    Nginx -->|proxy_pass| Gunicorn
    Gunicorn --> Django
    Django --> Postgres
    Django --> FS2[media/ volume]
    Django -->|OAuth requests| Google

    subgraph Docker Compose
        Nginx
        Gunicorn
        Django
        Postgres
        Redis[(Redis\nfuture use)]
    end
```

---

## Key files

| File | Responsibility |
|------|---------------|
| `google_media_backup/models.py` | `DriveAsset`, `MediaItem`, `RunLog` |
| `google_media_backup/api.py` | All Ninja endpoints — pipeline logic lives here |
| `google_media_backup/services_google.py` | Google API client, OAuth, Fernet token I/O |
| `google_media_backup/utils.py` | `sha256_file`, `deterministic_path`, `copy_into_media`, `get_fernet` |
| `google_media_backup/admin.py` | Django admin + custom ops console link |
| `config/settings.py` | All settings via `python-decouple` (`.env`) |
| `docker-compose.yml` | Postgres + Redis + Gunicorn + Nginx |
| `shared_context.md` | AI agent coordination — keep in sync |

---

## Critical invariants

- **Never skip a state.** The pipeline is append-only; each endpoint only processes its expected input state.
- **SHA-256 is the dedup key.** Two Drive files with identical content produce one `MediaItem`.
- **`photos:` prefix.** Google Photos IDs are stored as `"photos:<id>"` to prevent collision with Drive IDs.
- **Atomic download.** Files are written to `<path>.part` then `os.replace()`d — no partial files reach `DOWNLOADED`.
- **Retention guard is not bypassable without `force=true`.** Even then, `DRIVE_DELETE_MODE=trash` is the safe default.
- **`GOOGLE_ENCRYPTION_KEY` must be set and persisted.** Losing it makes the token unreadable.
