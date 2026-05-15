# shared_context.md
> Shared ground truth for Claude, Gemini, and Codex working on this repo.
> Keep this file updated as the project evolves.
> Last updated: 2026-05-14 (v0.5.0)

---

## What this project does

**backdeezup** is a backend-first pipeline that safely migrates media (photos, videos, documents) from a user's Google Drive / Google Photos into a local Django-managed storage, with a provable audit trail and a two-proof deletion guard before removing anything from Drive.

**Two proofs required before delete:**
1. The local file exists on disk
2. The file is recorded as a `MediaItem` in the database

---

## Data flow diagrams

### System overview

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

### State machine

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

### Data model (ER)

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

### Request/response sequence

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
    A->>G: Drive files().list
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

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 6.0+ |
| API | Django-Ninja 1.6+ (FastAPI-style, auto Swagger at `/api/docs`) |
| DB (dev) | SQLite (`db.sqlite3`) |
| DB (prod) | PostgreSQL 16 (via Docker Compose) |
| Google auth | `google-auth-oauthlib`, OAuth token encrypted with Fernet |
| File crypto | `cryptography.Fernet` (key = `GOOGLE_ENCRYPTION_KEY` env var) |
| Serving | Gunicorn + Whitenoise + Nginx |
| Containerization | Docker Compose (web + nginx + postgres + redis) |
| Package Manager | uv (Rust-based, 10-100x faster than pip) |
| Config | pyproject.toml (PEP 621) |
| Versioning | Semantic Versioning — CHANGELOG.md + VERSION file + git tags |
| Docs | MkDocs Material deployed to GitHub Pages via Actions |
| Browser tests | Playwright 1.59 + Chromium — installed and smoke-tested on WINWEB01 |
| Linting | pre-commit |

---

## Domain model

```
DriveAsset ──FK──> MediaItem
```

**`DriveAsset`** — one row per Google Drive / Photos item discovered.
Fields: `drive_id`, `name`, `mime_type`, `size_bytes`, `md5_checksum`, `download_path`, `state`, `error`, `media_item` (FK), timestamps.

**`MediaItem`** — deduplicated local file, keyed by `sha256`.
Fields: `sha256` (unique), `file` (FileField → `imported/`), `created_at`.

**`RunLog`** — audit log for each pipeline run.
Fields: `run_id`, `status`, `started_at`, `finished_at`, `totals` (JSON), `error_log` (JSON).

---

## State machine

```
DISCOVERED -> DOWNLOADED -> IMPORTED -> VERIFIED -> DELETE_PENDING -> DELETED
```

| State | Meaning |
|---|---|
| `DISCOVERED` | Found in Drive/Photos, not yet downloaded |
| `DOWNLOADED` | Binary on disk at `download_path` |
| `IMPORTED` | SHA-256 computed, copied to `media/imported/`, `MediaItem` created |
| `VERIFIED` | Both proofs confirmed (file on disk + MediaItem in DB) |
| `DELETE_PENDING` | Queued for Drive deletion (retention guard applies) |
| `DELETED` | Removed from Drive (trash or hard, per `DRIVE_DELETE_MODE`) |

**Retention guard:** `MIN_RETENTION_DAYS` (default: 3). An asset must be at least this many days old (from `imported_at`) before `commit-delete` acts on it.

---

## API endpoints (`/api`)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/connect` | Launch local OAuth flow, save encrypted token |
| `POST` | `/sync/discover` | Page through Drive images/videos, create `DriveAsset` rows |
| `POST` | `/sync/discover-files` | Same but for PDF, Office, archives, iWork docs |
| `POST` | `/sync/discover-photos` | Page through Google Photos Library (`photos:<id>` prefix) |
| `POST` | `/sync/download?limit=20` | Download `DISCOVERED` assets to local disk |
| `POST` | `/sync/import?limit=20` | SHA-256, copy to `media/imported/`, create `MediaItem` |
| `POST` | `/sync/verify?limit=50` | Confirm both proofs, advance to `VERIFIED` |
| `POST` | `/sync/mark-delete?limit=100` | Advance `VERIFIED` to `DELETE_PENDING` |
| `POST` | `/sync/commit-delete?force=false&limit=50` | Execute Drive deletion respecting retention guard |
| `GET` | `/assets?state=&q=` | List assets with optional state/name filter |

Swagger UI: `/api/docs`

---

## Key files

| File | Role |
|---|---|
| `backend_django/google_media_backup/models.py` | Django models: `DriveAsset`, `MediaItem`, `RunLog` |
| `backend_django/google_media_backup/api.py` | All Ninja API endpoints |
| `backend_django/google_media_backup/services_google.py` | Google Drive / Photos API wrappers, OAuth, Fernet token storage |
| `backend_django/google_media_backup/utils.py` | `sha256_file`, `deterministic_path`, `copy_into_media`, `get_fernet` |
| `backend_django/google_media_backup/admin.py` | Django admin with custom ops link |
| `backend_django/config/settings.py` | Django settings (all config via `python-decouple` + `.env`) |
| `docker-compose.yml` | Full stack: web + nginx + postgres + redis |
| `pyproject.toml` | Project config, dependencies, build settings (PEP 621) |
| `uv.lock` | Dependency lock file (managed by uv) |
| `dev.sh` / `dev.ps1` | Developer helper scripts (migrate, dev, test, etc.) |
| `CHANGELOG.md` | Release notes following Keep a Changelog format |
| `VERSION` | Current semantic version (0.3.0) |
| `docs/` | Full MkDocs documentation suite (10 pages) |
| `.github/workflows/gh-pages.yml` | Auto-deploy docs to GitHub Pages on push to main |
| `.github/workflows/ci.yml` | CI: Django checks + Playwright smoke test on every push/PR |
| `shared_context.md` | AI agent coordination — keep in sync |

---

## Important env vars

| Var | Default | Notes |
|---|---|---|
| `GOOGLE_CLIENT_SECRETS` | `secrets/google_client.json` | Path to OAuth client JSON |
| `GOOGLE_TOKEN_FILE` | `secrets/google_token.json` | Path for encrypted token |
| `GOOGLE_ENCRYPTION_KEY` | random (insecure) | 44-char Fernet key — set explicitly in prod |
| `GOOGLE_MIME_ALLOWLIST` | `image/jpeg` | Comma-separated MIME filter |
| `DRIVE_DELETE_MODE` | `trash` | `trash` or `hard` |
| `MIN_RETENTION_DAYS` | `3` | Minimum days before commit-delete fires |
| `DATABASE_URL` | SQLite fallback | Postgres URL in prod |
| `MEDIA_ROOT` | `backend_django/media` | Where imported files land |
| `DEBUG` | `True` (dev) | Set `False` in prod |

---

## Knowledge graph (graphify)

Built: 2026-05-12 — 86 nodes · 104 edges · 24 communities.
God nodes (most connected): `drive_service()`, `MediaItem`, `DriveAsset`, `RunLog`, `AssetOut`.
Refresh after code changes: `graphify update .`
Graph output: `graphify-out/` (graph.json, graph.html, GRAPH_REPORT.md)

---

## Future Roadmap (see docs/project-comparison.md)

### Phase 1: Foundation (HIGH PRIORITY)
- Multi-account model (`GoogleAccount`) with scope tracking
- Enhanced audit logs (actor, action, affected_count, affected_bytes)
- DB-backed settings management

### Phase 2: Reporting & Dashboards
- Admin dashboard with stats, quota tracking, top file types
- Materialized views for file type/size/age analysis
- CSV/JSON export capabilities

### Phase 3: Cleanup Rules Engine
- `CleanupRule` model with query filters
- Cleanup boards (Large+Old, Video, Duplicates)
- Dry-run then Execute workflow with confirmation

### Phase 4: Advanced Features
- SHA-256 duplicate detection (field exists, need logic)
- Incremental sync using Drive `changes.list()` API
- Proxy generation (720p thumbnails/previews)

### Phase 5: Automation
- Scheduled sync and cleanup (OFF by default)
- Protected lists (never-delete file types/paths)
- Quota tracking with color-coded UI

**Current version: 0.5.0** | **Target: v1.0.0 after Phase 3 complete**

---

## Conventions for AI agents

- **One pipeline step at a time.** Each API call advances exactly one state transition.
- **Never skip a state.** Deletion requires VERIFIED state; VERIFIED requires IMPORTED; etc.
- **SHA-256 is the dedup key.** `MediaItem.sha256` is unique — duplicate Drive files map to the same `MediaItem`.
- **`photos:` prefix.** Google Photos items use `drive_id = "photos:<id>"` to avoid collision with Drive IDs.
- **Settings via env.** All config is read via `python-decouple`; never hardcode.
- **Test DB is SQLite.** Use `DATABASE_URL` to point to Postgres in prod/Docker.
- **Graphify is installed for Claude, Gemini, and Codex.** Run `graphify update .` after any structural change so all agents stay in sync.
- **Use uv for dependencies.** Run `uv add <package>` — auto-updates pyproject.toml and uv.lock.
- **Use dev scripts.** `./dev.sh <command>` (Bash) or `.\dev.ps1 <command>` (PowerShell).
- **Update CHANGELOG.md.** Add under `[Unreleased]` as you work; move to versioned section on release.
- **Semantic versioning.** MAJOR.MINOR.PATCH — bump VERSION + pyproject.toml + tag + GitHub Release.
- **Git user: devadalberto** (devadalberto@gmail.com). Global account on machine is vertexchaos — local config overrides it.
- **Private GitHub repo.** https://github.com/devadalberto/backdeezup
- **Mermaid diagrams.** No `\n` in node labels, no Unicode arrows (use plain text). Required for GitHub renderer.
- **Playwright installed.** `playwright==1.59.0` + Chromium ready. Run via `uv run playwright`. No credentials needed for headless tests.
- **Server: WINWEB01.** Windows Server 2025, Hyper-V guest. HypervisorPlatform enabled. WSL2 running **Debian**, user: **saitama** (`\\wsl$\Debian\home\saitama`). SSH keys at `~/.ssh/` (copied from `C:\Users\Administrator\.ssh\`). Claude sandbox error resolved.
- **GitHub Pages disabled.** Private repo on free plan — Pages requires public. Docs workflow builds to artifact instead. Serve locally: `./dev.sh docs` on port 8001.
- **Cowork / Remote Control.** Start: `claude --remote-control backdeezup` from repo root. Join: `claude --resume WINWEB01/backdeezup` from another client.
- **docker-compose.yml** — all Postgres credentials come from `.env` via `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`, `${POSTGRES_DB}`. Never hardcoded. `web` waits for db healthcheck.
- **Production deploy** — full copy-paste steps in README: `.env` scaffold → build → up → migrate → createsuperuser → OAuth. `collectstatic` runs at container start via `entrypoint.sh`. Static files served by nginx from `/app/staticfiles/`.
- **entrypoint.sh** — runs `collectstatic` then starts gunicorn. Ensures static files always fresh on start.
- **secrets volume** — `./secrets:/app/backend_django/secrets:ro` mounted in docker-compose. Never baked into the image.
- **Debian WSL2 repo** — cloned at `/home/saitama/repos/github/devadalberto/backdeezup` (user: saitama).
- **Makefile** — `migrate`, `superuser`, `shell` run inside Docker via `docker compose exec web`. `run` and `docs` are local dev targets.
- **Admin UI (v0.5.0)** — `/admin/reports/` (live dashboard) and `/admin/ops/` (pipeline ops console) added via `admin_views.py` + templates.
- **Ubuntu remote** — hostname: DTC-5CG4155DQ9, IP: 192.168.88.20, user: jose, SSH port 2222 (WSL2 port-forward). Connect: `wsl -d Debian -- bash -c "ssh -p 2222 jose@192.168.88.20 '<cmd>'"`. Secrets path: `/home/jose/repos/github/devadalberto/gmail_cleanup/jose.valdes/secrets/`.
- **Google OAuth secrets** — copied to `secrets/` on both WINWEB01 and Debian WSL repos. Git-ignored, never committed.
- **OAuth headless flow** — `make auth` runs inside container. Uses `redirect_uri=http://localhost` (no port) to match the registered URI in `google_client.json` (type: installed/Desktop). Google redirects to `http://localhost/?code=...` — page fails to load, copy full URL from address bar, paste back. `OAUTHLIB_INSECURE_TRANSPORT=1` set in `start_oauth_local()`.
- **Google client secret policy (2025+)** — Google Cloud Console no longer shows or allows downloading existing client secrets. If `invalid_client` occurs, go to APIs & Services → Credentials → OAuth client → Add Secret → download updated JSON → replace `secrets/google_client.json`. Old secret cannot be recovered. See: https://support.google.com/cloud/answer/15549257#client-secret-hashing
- **Always check current Google API docs** before implementing or troubleshooting OAuth — Google changes policies frequently.
- **Google Cloud Console UI changed (2025+)** — old "APIs & Services → OAuth consent screen → Edit App" is gone. New path: **Google Auth Platform → Data Access → Add or remove scopes**. Clients at: **Google Auth Platform → Clients**.
- **OAuth client type MUST be Desktop app (installed)** — Web application clients block restricted scopes (photoslibrary.readonly, gmail.modify) unless HTTPS redirect URIs are used. Always use Desktop app type. Current Desktop app client: `486053539237-c454bqj13or711a74tfc8t493qlna64d.apps.googleusercontent.com` (named `backdeezup-desktop`).
- **Copying new google_client.json from Windows Downloads to Debian** — Google downloads files with `(1)` suffix when file already exists. Always copy the `(1).json` version: `cp '/mnt/c/Users/Administrator/Downloads/client_secret_486053539237-c454bqj13or711a74tfc8t493qlna64d.apps.googleusercontent.com (1).json' ~/repos/github/devadalberto/backdeezup/secrets/google_client.json`
- **Verify client type before auth** — run `python3 -c "import json; d=json.load(open('secrets/google_client.json')); print(list(d.keys())[0])"` — must print `installed`, not `web`.
- **google_gmail_backup app** — Gmail backup Django app alongside `google_media_backup`. Models: `GmailMessage`, `GmailAttachment`, `GmailSyncState`. API at `/api/gmail/*`. Full snapshot + historyId incremental sync. Stores .eml files at `gmail/<account>/<year>/<month>/<id>.eml`.
- **Tests** — 23 unit tests across both apps. Run: `make test`. CI: lint (ruff) + tests + Playwright smoke on every push/PR.
- **make preflight** — checks Docker running, .env present, no CHANGE_ME, google_client.json is type `installed`. Run before every deploy.
- **make sync-run** — full pipeline loop (download→import→verify) with ASCII progress bar. LIMIT=100 default, override with `make sync-run LIMIT=200`.
- **make sync-run LIMIT=X** — override batch size. 100 safe, 500 causes 504 timeout.
- **GET /api/progress** — returns pipeline counts and % verified across all states.
- **Google Photos blocked** — photoslibrary.readonly scope blocked because old web client (1ql0o9aj) still has non-HTTPS redirect URIs in the project. Project-wide restriction. Photos skipped for now.
- **Google Auth Platform** (new UI 2025+) — replaces "APIs & Services → OAuth consent screen". Scopes at: Google Auth Platform → Data Access → Add or remove scopes.
- **Desktop app OAuth client** — client_id: `486053539237-c454bqj13or711a74tfc8t493qlna64d`, named `backdeezup-desktop`. MUST be `installed` type, not `web`.
- **Current pipeline status** — 548/2176 verified (25.2%) as of 2026-05-15. Running `make sync-run` to complete.
- **Current version: 0.6.4**
