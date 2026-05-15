# backdeezup

A backend-first pipeline that safely migrates media from **Google Drive / Google Photos** into local Django-managed storage, with a provable audit trail and a two-proof deletion guard before anything is removed from Drive.

> **Two proofs required before any delete:**
> 1. Local file exists on disk
> 2. File is recorded as a `MediaItem` in the database

[![GitHub release](https://img.shields.io/github/v/release/devadalberto/backdeezup)](https://github.com/devadalberto/backdeezup/releases)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-6.0%2B-green)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

---

## How it works

```mermaid
flowchart LR
    GD[(Google Drive / Photos)]
    API[Django-Ninja API]
    DB[(Database)]
    FS[Local Storage]
    AD[Django Admin]

    GD -->|OAuth + Drive v3| API
    API -->|state transitions| DB
    API -->|binary download + SHA-256| FS
    AD -->|manage and monitor| DB
```

### Pipeline state machine

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

### Data model

```mermaid
erDiagram
    DriveAsset {
        string  drive_id       PK
        string  name
        string  mime_type
        bigint  size_bytes
        string  md5_checksum
        string  download_path
        string  state
        text    error
        int     media_item_id  FK
        datetime discovered_at
        datetime downloaded_at
        datetime imported_at
        datetime last_attempt_at
    }
    MediaItem {
        int      id        PK
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

### Request / response flow

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
    A->>FS: save Fernet-encrypted token
    A-->>C: OAuth completed

    C->>A: POST /sync/discover
    A->>G: files().list
    G-->>A: files + nextPageToken
    A->>DB: DriveAsset get_or_create DISCOVERED
    A-->>C: discovered N, run_id

    C->>A: POST /sync/download
    A->>G: files().get_media
    G-->>A: binary stream
    A->>FS: write .part then rename
    A->>DB: state DOWNLOADED
    A-->>C: downloaded N

    C->>A: POST /sync/import
    A->>FS: sha256_file + copy_into_media
    A->>DB: MediaItem get_or_create
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

## Operational runbook (production)

### First-time deployment

```bash
# 1. Clone
git clone git@github.com:devadalberto/backdeezup.git
cd backdeezup

# 2. Configure
cp .env.sample .env
vim .env   # fill all CHANGE_ME values
# Generate Django secret key:
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
# Generate Fernet key (stdlib, no deps needed):
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 3. Place Google Desktop app credentials (type must be 'installed', not 'web')
# Download from Google Auth Platform → Clients → backdeezup-desktop → Download JSON
# If file already exists in Downloads, Google adds (1) suffix — use that one:
cp '/mnt/c/Users/Administrator/Downloads/client_secret_*_(1).json' secrets/google_client.json
# Verify type:
python3 -c "import json; d=json.load(open('secrets/google_client.json')); print(list(d.keys())[0])"
# Must print: installed

# 4. Pre-flight check
make preflight

# 5. Build and start
make build && make up
make migrate && make superuser

# 6. Authenticate with Google
make auth
# Opens browser URL — approve all scopes — copy redirect URL back to terminal

# 7. Verify auth
curl -s http://localhost:8844/api/gmail/profile
```

### Running the backup pipeline

```bash
# Drive + Photos discovery
make discover
make discover-files

# Full Drive pipeline loop (runs until 100%)
while make sync-run; do sleep 1; done

# Check Drive progress anytime
make progress

# Gmail discovery (fast — stores IDs only)
make gmail-discover

# Full Gmail pipeline loop (runs until 100%)
while make gmail-run; do sleep 1; done

# Check Gmail progress anytime
make gmail-progress
```

### Subsequent runs (incremental)

```bash
make redeploy           # pull latest + rebuild + restart
make gmail-discover     # pick up new messages since last run
while make gmail-run; do sleep 1; done
```

---

## Quick start

### Local dev (uv — recommended)

```bash
# 1. Install dependencies (uv manages the venv automatically)
uv sync

# 2. Configure environment
cp .env.sample .env
# Edit .env — set GOOGLE_ENCRYPTION_KEY (44-char Fernet key)
# python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# 3. Place Google OAuth credentials
cp ~/Downloads/client_secret_*.json secrets/google_client.json

# 4. Run migrations and start
./dev.sh migrate      # Windows: .\dev.ps1 migrate
./dev.sh dev          # http://localhost:8844

# 5. Complete OAuth
# Open http://localhost:8844/api/docs -> POST /auth/connect
```

### Development commands

```bash
# Bash (Linux / Mac / WSL)
./dev.sh dev | migrate | makemigrations | superuser | shell | test | docs

# PowerShell (Windows)
.\dev.ps1 dev | migrate | makemigrations | superuser | shell | test | docs

# Add a dependency
./dev.sh add django-extensions
```

### Docker (prod-like)

```bash
make build && make up   # postgres + nginx on :8844
make migrate && make superuser
```

---

## Production deployment

### 1. Create `.env`

Copy this block, fill in every `CHANGE_ME` value, then save as `.env` in the repo root:

```env
# ── Django ────────────────────────────────────────────────────────────────────
DJANGO_SECRET_KEY=CHANGE_ME_long_random_50_char_string
DEBUG=False
ALLOWED_HOSTS=CHANGE_ME_your_server_hostname_or_ip,localhost
CSRF_TRUSTED_ORIGINS=http://CHANGE_ME_your_server_hostname_or_ip:8844

# ── Database ──────────────────────────────────────────────────────────────────
POSTGRES_USER=backdeezup
POSTGRES_PASSWORD=CHANGE_ME_db_password
POSTGRES_DB=backdeezup
DATABASE_URL=postgres://backdeezup:CHANGE_ME_db_password@db:5432/backdeezup

# ── Google OAuth ──────────────────────────────────────────────────────────────
GOOGLE_ENCRYPTION_KEY=CHANGE_ME_run_keygen_below
GOOGLE_CLIENT_SECRETS=secrets/google_client.json
GOOGLE_TOKEN_FILE=secrets/google_token.json
GOOGLE_MIME_ALLOWLIST=image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime,video/x-msvideo

# ── Pipeline behaviour ────────────────────────────────────────────────────────
DRIVE_DELETE_MODE=trash
MIN_RETENTION_DAYS=3

# ── Storage ───────────────────────────────────────────────────────────────────
MEDIA_ROOT=/app/media
STATIC_ROOT=/app/staticfiles

# ── Admin UI labels (optional) ───────────────────────────────────────────────
ADMIN_SITE_HEADER=BackDeezUp
ADMIN_SITE_TITLE=BackDeezUp Admin
ADMIN_INDEX_TITLE=Dashboard
SWAGGER_TITLE=BackDeezUp API
SWAGGER_VERSION=0.4.0
```

Generate the Fernet key for `GOOGLE_ENCRYPTION_KEY`:

```bash
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Generate a Django secret key:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> **Important:** Store `.env` and `secrets/` outside version control. Both are git-ignored.

---

### 2. Place Google OAuth credentials

```bash
mkdir -p secrets
cp ~/Downloads/client_secret_*.json secrets/google_client.json
```

---

### 3. Build and start

```bash
# Build image (runs collectstatic automatically)
docker compose build

# Start all services: postgres + redis + web + nginx
docker compose up -d

# Verify all containers are healthy
docker compose ps
```

---

### 4. Run migrations

```bash
docker compose exec web python manage.py migrate
```

---

### 5. Create superuser

```bash
docker compose exec web python manage.py createsuperuser
```

---

### 6. Authenticate with Google

```bash
# Open the Swagger UI in a browser and call POST /auth/connect
open http://localhost:8844/api/docs
# OR trigger it directly:
curl -X POST http://localhost:8844/api/auth/connect
```

Complete the OAuth browser flow. The encrypted token is saved to `secrets/google_token.json` inside the container volume.

---

### 7. Verify the deployment

```bash
# Static files served by nginx (should return 200)
curl -I http://localhost:8844/static/admin/css/base.css

# API health / Swagger UI
curl -I http://localhost:8844/api/docs

# Django Admin
curl -I http://localhost:8844/admin/
```

---

### Ongoing operations

```bash
# Tail logs
docker compose logs -f --tail=100

# Restart after a code change
docker compose build web && docker compose up -d web

# Apply new migrations after a code change
docker compose exec web python manage.py migrate

# Open Django shell
docker compose exec web python manage.py shell

# Stop everything
docker compose down

# Stop and wipe the database volume (destructive)
docker compose down -v
```

---

## API reference

Base: `http://localhost:8844/api` — Swagger UI at `/api/docs`

| Method | Endpoint | Key params | Advances state |
|--------|----------|------------|----------------|
| `POST` | `/auth/connect` | — | OAuth |
| `POST` | `/sync/discover` | `page_size`, `max_pages` | DISCOVERED |
| `POST` | `/sync/discover-files` | `page_size`, `max_pages` | DISCOVERED |
| `POST` | `/sync/discover-photos` | `page_size`, `max_pages` | DISCOVERED |
| `POST` | `/sync/download` | `limit=20` | DOWNLOADED |
| `POST` | `/sync/import` | `limit=20` | IMPORTED |
| `POST` | `/sync/verify` | `limit=50` | VERIFIED |
| `POST` | `/sync/mark-delete` | `limit=100` | DELETE_PENDING |
| `POST` | `/sync/commit-delete` | `force=false`, `limit=50` | DELETED |
| `GET`  | `/assets` | `state=`, `q=` | read-only |

---

## Configuration

Copy `.env.sample` to `.env`:

| Variable | Default | Required | Notes |
|----------|---------|----------|-------|
| `DJANGO_SECRET_KEY` | `insecure-key` | prod | Random 50-char string |
| `GOOGLE_ENCRYPTION_KEY` | — | **yes** | 44-char Fernet key — generate once, never lose |
| `GOOGLE_CLIENT_SECRETS` | `secrets/google_client.json` | **yes** | OAuth client JSON from Google Cloud |
| `GOOGLE_TOKEN_FILE` | `secrets/google_token.json` | auto | Written by `/auth/connect` |
| `GOOGLE_MIME_ALLOWLIST` | `image/jpeg,...` | no | Comma-separated MIME filter |
| `DRIVE_DELETE_MODE` | `trash` | no | `trash` (recoverable) or `hard` (permanent) |
| `MIN_RETENTION_DAYS` | `3` | no | Days before commit-delete fires |
| `DATABASE_URL` | SQLite | prod | `postgres://user:pass@host/db` |
| `MEDIA_ROOT` | `media` | no | Where imported files land |
| `DEBUG` | `false` | no | Never `true` in prod |

---

## Project structure

```
backdeezup/
├── backend_django/
│   ├── config/
│   │   ├── settings.py          # python-decouple config
│   │   └── urls.py              # /admin  /api  /admin/ops
│   └── google_media_backup/
│       ├── models.py            # DriveAsset, MediaItem, RunLog
│       ├── api.py               # All Ninja endpoints
│       ├── services_google.py   # Drive/Photos OAuth + Fernet
│       ├── utils.py             # sha256_file, deterministic_path
│       ├── admin.py             # Admin registrations
│       └── admin_ops.py         # Staff-only ops console
├── docs/                        # MkDocs source
├── secrets/                     # OAuth credentials (git-ignored)
├── nginx/nginx.conf
├── docker-compose.yml
├── pyproject.toml               # uv / PEP 621
├── dev.sh / dev.ps1             # Developer helper scripts
├── CHANGELOG.md
└── shared_context.md            # AI agent coordination
```

---

## Modern tooling

Powered by **[uv](https://docs.astral.sh/uv/)** — Rust-based, 10-100x faster than pip:

- Automatic virtual environment management
- Lock file (`uv.lock`) for reproducible builds
- `pyproject.toml`-first (PEP 621)

Use `uv add <package>` to add dependencies.

---

## AI agent collaboration

Claude, Gemini CLI, and Codex work this repo in parallel.

- **`shared_context.md`** — canonical ground truth; update when architecture changes
- **`graphify-out/`** — knowledge graph (86 nodes, 104 edges); run `graphify update .` after code changes
- Agent config files: `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`

---

## Acknowledgements

- [Django](https://www.djangoproject.com/) and [Django Ninja](https://django-ninja.dev/) for the API layer
- [Google APIs Python Client](https://github.com/googleapis/google-api-python-client) for Drive and Photos integration
- [uv](https://docs.astral.sh/uv/) by Astral for blazing-fast Python package management
- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) for documentation
- [Fernet (cryptography)](https://cryptography.io/) for token encryption
