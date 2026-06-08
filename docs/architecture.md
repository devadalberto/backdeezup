# Architecture

---

## System overview

BackDeezUp is an API-first Django application. The Django-Ninja layer is the primary interface; Django Admin provides a secondary ops console for browsing and managing state.

```mermaid
flowchart LR
    GD[(Google Drive / Photos)]
    API[Django-Ninja API port 8844]
    DB[(Postgres / SQLite)]
    FS[Local Storage media/]
    AD[Django Admin]
    SW[Swagger UI /api/docs]

    GD -->|OAuth 2.0| API
    SW -->|HTTP| API
    API -->|state transitions| DB
    API -->|binary + SHA-256 copy| FS
    AD -->|read / manage| DB
```

---

## Pipeline state machine

Every `DriveAsset` row progresses through exactly six states. No state can be skipped. Each API endpoint only processes assets in its expected input state.

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

| State | Meaning | Set by |
|---|---|---|
| `DISCOVERED` | Found in Drive/Photos, not yet downloaded | `/sync/discover*` |
| `DOWNLOADED` | Binary file on disk at `download_path` | `/sync/download` |
| `IMPORTED` | SHA-256 computed, copied to `media/imported/`, `MediaItem` created | `/sync/import` |
| `VERIFIED` | Both proofs confirmed | `/sync/verify` |
| `DELETE_PENDING` | Queued for Drive deletion | `/sync/mark-delete` |
| `DELETED` | Removed from Drive (trash or hard) | `/sync/commit-delete` |

---

## Two-proof deletion guard

Before any file is deleted from Google Drive, the system independently verifies:

1. **Disk proof** — `os.path.exists(download_path)` returns `True`
2. **Database proof** — `MediaItem.objects.filter(id=asset.media_item_id).exists()` returns `True`

If either check fails the asset stays in `DOWNLOADED`/`IMPORTED` and the error is recorded. Only assets where **both** proofs pass advance to `VERIFIED`.

---

## Full request / response sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant G as Google
    participant DB as Database
    participant FS as File System

    C->>A: POST /auth/connect
    A->>G: InstalledAppFlow OAuth
    G-->>A: credentials
    A->>FS: Fernet-encrypted token saved
    A-->>C: OAuth completed

    C->>A: POST /sync/discover
    A->>G: files().list
    G-->>A: files + nextPageToken
    A->>DB: DriveAsset get_or_create DISCOVERED
    A-->>C: discovered N

    C->>A: POST /sync/download
    A->>G: files().get_media
    G-->>A: binary stream
    A->>FS: write to .part then rename
    A->>DB: state DOWNLOADED
    A-->>C: downloaded N

    C->>A: POST /sync/import
    A->>FS: sha256_file + copy_into_media
    A->>DB: MediaItem get_or_create by sha256
    A->>DB: DriveAsset state IMPORTED
    A-->>C: imported N

    C->>A: POST /sync/verify
    A->>FS: os.path.exists proof 1
    A->>DB: MediaItem.exists proof 2
    A->>DB: state VERIFIED
    A-->>C: verified N

    C->>A: POST /sync/mark-delete
    A->>DB: state DELETE_PENDING
    A-->>C: queued N

    C->>A: POST /sync/commit-delete
    A->>DB: check retention days
    A->>G: trash or hard delete
    A->>DB: state DELETED
    A-->>C: deleted N
```

---

## Data model

```mermaid
erDiagram
    DriveAsset {
        string   drive_id       PK
        string   name
        string   mime_type
        bigint   size_bytes
        string   md5_checksum
        string   download_path
        string   state
        text     error
        int      media_item_id  FK
        datetime discovered_at
        datetime downloaded_at
        datetime imported_at
        datetime last_attempt_at
    }
    MediaItem {
        int      id         PK
        string   sha256
        string   file
        datetime created_at
    }
    RunLog {
        string   run_id     PK
        string   status
        json     totals
        json     error_log
        datetime started_at
        datetime finished_at
    }
    DriveAsset }o--|| MediaItem : "media_item SET NULL"
```

---

## Deployment topology

```mermaid
flowchart TD
    Browser -->|port 8844| Nginx
    Nginx -->|proxy_pass| Gunicorn
    Gunicorn --> Django
    Django --> Postgres
    Django --> FS2[media/ volume]
    Django -->|OAuth| Google

    subgraph Docker Compose
        Nginx
        Gunicorn
        Django
        Postgres
        Redis[(Redis future use)]
    end
```

---

## Key files

| File | Responsibility |
|---|---|
| `google_media_backup/models.py` | `DriveAsset`, `MediaItem`, `RunLog` |
| `google_media_backup/api.py` | All Ninja endpoints — pipeline logic |
| `google_media_backup/services_google.py` | Google API client, OAuth, Fernet token I/O |
| `google_media_backup/utils.py` | `sha256_file`, `deterministic_path`, `copy_into_media`, `get_fernet` |
| `google_media_backup/admin.py` | Django admin + ops console link |
| `config/settings.py` | All settings via python-decouple |
| `docker-compose.yml` | Postgres + Redis + Gunicorn + Nginx |

---

## Critical invariants

- **Never skip a state.** Each endpoint only processes its expected input state.
- **SHA-256 is the dedup key.** Two Drive files with identical content produce one `MediaItem`.
- **`photos:` prefix.** Google Photos IDs stored as `photos:<id>` to avoid collision with Drive IDs.
- **Atomic download.** Files written to `<path>.part` then `os.replace()` — no partial files reach `DOWNLOADED`.
- **Retention guard is not bypassable without `force=true`.** Even then, `DRIVE_DELETE_MODE=trash` is the safe default.
- **`GOOGLE_ENCRYPTION_KEY` must be persisted.** Losing it makes the OAuth token unreadable.
