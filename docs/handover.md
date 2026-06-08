# Handover & Architecture

> Last updated: 2026-05-13 (v0.2.0)

This document is the canonical reference for anyone (human or AI agent) picking up this codebase. It covers architecture, invariants, and operational context.

---

## What this system does

**BackDeezUp** is a backend-first pipeline that safely migrates media from Google Drive / Google Photos into local Django-managed storage, then deletes the originals from Drive only after two independent proofs of local safety are confirmed.

**Two proofs required before any Drive delete:**

1. Local file exists at `download_path` on disk
2. A `MediaItem` row exists in the database (keyed by SHA-256)

---

## System overview

```mermaid
flowchart LR
    GD[(Google Drive / Photos)]
    API[Django-Ninja API port 8844]
    DB[(Database)]
    FS[Local Storage media/]
    AD[Django Admin + Ops Console]

    GD -->|OAuth + Drive v3| API
    API -->|state transitions| DB
    API -->|binary download + SHA-256 copy| FS
    AD -->|manage and monitor| DB
```

---

## Pipeline state machine

Each `DriveAsset` row moves through exactly these states. No state can be skipped.

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
    A->>FS: write .part then rename
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
        Redis[(Redis)]
    end
```

---

## Key files

| File | Responsibility |
|---|---|
| `google_media_backup/models.py` | `DriveAsset`, `MediaItem`, `RunLog` |
| `google_media_backup/api.py` | All Ninja endpoints |
| `google_media_backup/services_google.py` | Google API client, OAuth, Fernet token I/O |
| `google_media_backup/utils.py` | `sha256_file`, `deterministic_path`, `copy_into_media`, `get_fernet` |
| `google_media_backup/admin.py` | Django admin + ops console link |
| `config/settings.py` | All settings via python-decouple |
| `docker-compose.yml` | Postgres + Redis + Gunicorn + Nginx |
| `shared_context.md` | AI agent coordination — keep in sync |
| `pyproject.toml` | Dependencies + build config (uv / PEP 621) |

---

## Critical invariants

- **Never skip a state.** Each endpoint only processes its expected input state.
- **SHA-256 is the dedup key.** Two Drive files with identical content produce one `MediaItem`.
- **`photos:` prefix.** Google Photos IDs stored as `photos:<id>` to prevent Drive ID collision.
- **Atomic download.** Files written to `<path>.part` then `os.replace()` — no partial files reach `DOWNLOADED`.
- **Retention guard.** `MIN_RETENTION_DAYS` enforced unless `force=true` is explicitly passed.
- **`GOOGLE_ENCRYPTION_KEY` must be persisted.** Losing it makes the OAuth token unreadable.
