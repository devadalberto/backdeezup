# backdeezup

A backend-first pipeline that safely migrates media from **Google Drive / Google Photos** into local Django-managed storage, with a provable audit trail and a two-proof deletion guard before anything is removed from Drive.

> **Two proofs required before any delete:**
> 1. Local file exists on disk
> 2. File is recorded as a `MediaItem` in the database

---

## How it works

```mermaid
flowchart LR
    GD[(Google Drive\n/ Photos)]
    API[Django-Ninja\nAPI]
    DB[(Database\nDriveAsset\nMediaItem\nRunLog)]
    FS[Local\nFile Storage\nmedia/imported/]
    AD[Django Admin\n+ Ops Console]

    GD -->|OAuth + Drive v3\nPhotos Library API| API
    API -->|state transitions| DB
    API -->|binary download\nSHA-256 copy| FS
    AD -->|manage & monitor| DB
```

### Pipeline state machine

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED : /sync/discover\n/sync/discover-files\n/sync/discover-photos

    DISCOVERED --> DOWNLOADED : /sync/download\n(Drive → local disk)

    DOWNLOADED --> IMPORTED : /sync/import\n(SHA-256 + copy to media/imported/\ncreates MediaItem)

    IMPORTED --> VERIFIED : /sync/verify\n(proof 1: file on disk\nproof 2: MediaItem in DB)

    VERIFIED --> DELETE_PENDING : /sync/mark-delete

    DELETE_PENDING --> DELETED : /sync/commit-delete\n(retention guard: MIN_RETENTION_DAYS)\n(mode: trash | hard)

    DISCOVERED --> DISCOVERED : error → retry
    DOWNLOADED --> DOWNLOADED : error → retry
```

### Data model

```mermaid
erDiagram
    DriveAsset {
        string  drive_id       PK "unique Drive / photos: ID"
        string  name
        string  mime_type
        bigint  size_bytes
        string  md5_checksum
        string  download_path
        string  state          "DISCOVERED → … → DELETED"
        text    error
        int     media_item_id  FK
        datetime discovered_at
        datetime downloaded_at
        datetime imported_at
        datetime last_attempt_at
    }
    MediaItem {
        int    id       PK
        string sha256   "unique — dedup key"
        file   file     "media/imported/<sha[:2]>/<sha>.ext"
        datetime created_at
    }
    RunLog {
        string   run_id      PK "UUID"
        string   status      "RUNNING | OK | ERROR"
        json     totals
        json     error_log
        datetime started_at
        datetime finished_at
    }
    DriveAsset }o--|| MediaItem : "media_item (SET NULL)"
```

### Request → response flow for a full pipeline run

```mermaid
sequenceDiagram
    participant C as Client
    participant A as Django-Ninja API
    participant G as Google API
    participant DB as Database
    participant FS as File System

    C->>A: POST /auth/connect
    A->>G: InstalledAppFlow OAuth
    G-->>A: credentials
    A->>FS: save Fernet-encrypted token
    A-->>C: "OAuth completed"

    C->>A: POST /sync/discover
    A->>G: Drive files().list (images/videos)
    G-->>A: page of files + nextPageToken
    A->>DB: DriveAsset get_or_create (state=DISCOVERED)
    A-->>C: {discovered: N, run_id: ...}

    C->>A: POST /sync/download?limit=20
    A->>G: files().get_media (per asset)
    G-->>A: binary stream
    A->>FS: write .part → rename to final path
    A->>DB: state = DOWNLOADED
    A-->>C: {downloaded: N}

    C->>A: POST /sync/import?limit=20
    A->>FS: sha256_file(), copy_into_media()
    A->>DB: MediaItem get_or_create (sha256)
    A->>DB: DriveAsset.media_item = FK, state = IMPORTED
    A-->>C: {imported: N}

    C->>A: POST /sync/verify?limit=50
    A->>FS: os.path.exists(download_path)
    A->>DB: MediaItem.objects.filter(id=...).exists()
    A->>DB: state = VERIFIED (both proofs pass)
    A-->>C: {verified: N}

    C->>A: POST /sync/mark-delete?limit=100
    A->>DB: state = DELETE_PENDING
    A-->>C: {queued_for_delete: N}

    C->>A: POST /sync/commit-delete
    A->>DB: check (now - imported_at).days >= MIN_RETENTION_DAYS
    A->>G: files().update trashed=true  OR  files().delete
    A->>DB: state = DELETED
    A-->>C: {deleted: N, mode: trash|hard}
```

---

## Quick start

### Local dev

```bash
# 1. Install dependencies
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 2. Configure environment
cp .env.sample .env
# Edit .env — set GOOGLE_ENCRYPTION_KEY (44-char Fernet key)
# Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. Place Google OAuth credentials
# Download client_secret_*.json from Google Cloud Console → rename to:
cp ~/Downloads/client_secret_*.json secrets/google_client.json

# 4. Run migrations and start
make migrate
make run          # http://localhost:8844

# 5. Complete OAuth
# Open http://localhost:8844/api/docs → POST /auth/connect
```

### Docker (prod-like)

```bash
make build
make up           # postgres + nginx on :8844
make migrate
make superuser
```

---

## API reference

Base: `http://localhost:8844/api` — Swagger UI at `/api/docs`

| Method | Endpoint | Key params | Advances state |
|--------|----------|------------|----------------|
| `POST` | `/auth/connect` | — | — (OAuth) |
| `POST` | `/sync/discover` | `page_size`, `max_pages` | → `DISCOVERED` |
| `POST` | `/sync/discover-files` | `page_size`, `max_pages` | → `DISCOVERED` |
| `POST` | `/sync/discover-photos` | `page_size`, `max_pages` | → `DISCOVERED` |
| `POST` | `/sync/download` | `limit=20` | → `DOWNLOADED` |
| `POST` | `/sync/import` | `limit=20` | → `IMPORTED` |
| `POST` | `/sync/verify` | `limit=50` | → `VERIFIED` |
| `POST` | `/sync/mark-delete` | `limit=100` | → `DELETE_PENDING` |
| `POST` | `/sync/commit-delete` | `force=false`, `limit=50` | → `DELETED` |
| `GET`  | `/assets` | `state=`, `q=` | — (read) |

---

## Configuration

Copy `.env.sample` → `.env` and set:

| Variable | Default | Required | Notes |
|----------|---------|----------|-------|
| `DJANGO_SECRET_KEY` | `insecure-key` | **prod** | Random 50-char string |
| `GOOGLE_ENCRYPTION_KEY` | random | **yes** | 44-char Fernet key; generate once, keep forever |
| `GOOGLE_CLIENT_SECRETS` | `secrets/google_client.json` | **yes** | OAuth client JSON from Google Cloud |
| `GOOGLE_TOKEN_FILE` | `secrets/google_token.json` | auto | Written by `/auth/connect` |
| `GOOGLE_MIME_ALLOWLIST` | `image/jpeg,...` | no | Comma-separated MIME types to discover |
| `DRIVE_DELETE_MODE` | `trash` | no | `trash` (recoverable) or `hard` (permanent) |
| `MIN_RETENTION_DAYS` | `3` | no | Days asset must be held locally before Drive delete |
| `DATABASE_URL` | SQLite | prod | `postgres://user:pass@host/db` |
| `MEDIA_ROOT` | `media` | no | Local directory for imported files |
| `DEBUG` | `false` | no | Never `true` in prod |

---

## Project structure

```
backdeezup/
├── backend_django/
│   ├── config/
│   │   ├── settings.py          # All config via python-decouple
│   │   └── urls.py              # Routes: /admin /api /admin/ops /
│   └── google_media_backup/
│       ├── models.py            # DriveAsset, MediaItem, RunLog
│       ├── api.py               # All Ninja endpoints
│       ├── services_google.py   # Drive/Photos API + OAuth + Fernet token
│       ├── utils.py             # sha256_file, deterministic_path, get_fernet
│       ├── admin.py             # Django admin registrations + ops link
│       └── admin_ops.py        # Staff-only ops console view
├── secrets/                     # OAuth credentials (git-ignored in prod)
├── docs/                        # MkDocs source (published to GitHub Pages)
├── nginx/nginx.conf
├── docker-compose.yml
├── Makefile
├── requirements.txt
└── shared_context.md            # AI agent coordination file
```

---

## Make targets

```bash
make run        # python manage.py runserver 0.0.0.0:8844
make migrate    # python manage.py migrate
make superuser  # python manage.py createsuperuser
make build      # docker compose build
make up         # docker compose up -d
make down       # docker compose down
make logs       # docker compose logs -f --tail=100
make docs       # mkdocs serve -a 0.0.0.0:8001
```

---

## AI agent collaboration

This repo is worked on by **Claude**, **Gemini CLI**, and **Codex** in parallel.

- **`shared_context.md`** — canonical ground truth for all agents; update it when architecture changes
- **`graphify-out/`** — knowledge graph (86 nodes, 104 edges); refresh with `graphify update .` after code changes
- Graphify is registered for all three agents via their respective instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`)
