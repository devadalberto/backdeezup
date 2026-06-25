# shared_context.md
> Shared ground truth for Claude, Gemini, and Codex working on this repo.
> Keep this file updated as the project evolves.
> Last updated: 2026-05-19 (v0.11.0)

---

## What this project does

**backdeezup** is a self-hosted Django platform that safely backs up Google Drive/Photos/Gmail, runs intelligent cleanup rules, and provides a Wagtail media vault with a Stash-style gallery. Production-grade: Celery workers, TLS, Sentry, Redis auth, atomic token writes, EXIF stripping.

---

## Apps

| App | Models | Purpose |
|---|---|---|
| `google_media_backup` | DriveAsset, MediaItem, RunLog | Drive + Photos backup pipeline |
| `google_gmail_backup` | GmailMessage, GmailAttachment, CleanupRule, RuleCondition, ProtectedSender, CleanupAuditLog | Gmail backup + cleanup engine |
| `media_vault` | VaultImage, VaultMedia, VaultDocument, MediaDecision, MediaMetadata, GalleryIndexPage | Wagtail 7.4 vault + EXIF strip + gallery |
| `accounts` | BackupUser | Custom user model |
| `core` | — | Landing page, HTMX stats |

---

## Pipeline status (2026-05-19)

| Pipeline | Status |
|---|---|
| Drive | 2176/2176 verified — COMPLETE |
| Gmail | ~25k/32,463 verified (78%) — loop running, trash emptied |
| Photos | BLOCKED — delete old web client `1ql0o9aj` from Google Auth Platform → Clients |

---

## Infrastructure stack

| Service | Details |
|---|---|
| Web | Gunicorn + Django 6.0 + Django-Ninja |
| Nginx | TLS 1.2/1.3, HTTP→HTTPS redirect, `internal` media location |
| PostgreSQL 16 | Primary DB, healthchecked |
| Redis 7 | Password-protected, 256MB limit, Celery broker + rate-limit cache |
| Celery worker | 2 concurrent, replaces APScheduler, retries on failure |
| Celery Beat | `django_celery_beat` scheduler, schedule editable in admin |

**Ports:** HTTPS `8445`, HTTP `8844` (redirects), OAuth callback `18444`

**TLS:** Self-signed cert at `nginx/certs/` (git-ignored). Generate: `make gen-certs`. Installed to Windows Trusted Root via `certutil`.

**Sentry:** `SENTRY_DSN` env var — blank = disabled. Django + Celery + Redis integrations.

---

## Key URLs

| URL | Purpose |
|---|---|
| `https://localhost:8445` | Main entry (HTTPS) |
| `/admin/` | Django Admin (Matrix + Amber theme) |
| `/admin/gmail/dashboard/` | Gmail progress bar (HTMX 15s refresh) |
| `/admin/gmail/ops/` | Gmail ops — pipeline, rules, empty trash |
| `/admin/gmail/rule-builder/` | Compound rule builder |
| `/admin/ops/` | Drive ops console |
| `/admin/vault/ops/` | Vault ops — import + review links |
| `/vault/gallery/` | Stash-style gallery (thumbnail grid, filters, video streaming) |
| `/vault/review/` | Media triage (K/D/S/Z) |
| `/cms/` | Wagtail CMS |
| `/admin/django_celery_beat/` | Edit periodic task schedule |
| `/api/docs` | Drive API Swagger |
| `/api/gmail/docs` | Gmail API Swagger |
| `/api/vault/docs` | Vault API Swagger |

---

## Key make targets

```bash
make preflight                        # ALWAYS run first
make build && make up                 # start stack
make redeploy                         # pull+build+restart+migrate (standard upgrade)
make gen-certs                        # generate self-signed TLS cert (once)
make auth                             # Google OAuth (Desktop app client)
make migrate                          # run migrations only
make seed-rules                       # seed/update 15 core cleanup rules (idempotent)
make seed-inbox-rules                 # seed/update 12 inbox-specific rules (idempotent)
make vault-setup                      # create Wagtail VaultHomePage (once)
make gmail-discover                   # discover all Gmail IDs (50 pages × 500)
make gmail-loop LIMIT=500 WORKERS=10  # concurrent download+verify until done
make gmail-extract-attachments-dry    # count extractable attachments
make gmail-extract-attachments        # extract family images/videos from .eml
make import-media                     # import Drive+Gmail media → Wagtail vault
make celery-logs                      # tail worker + beat output
make celery-status                    # inspect active tasks
make test-full                        # lint + 59 unit tests (before every PR)
```

---

## SSH / Git config

**Machines:** WINWEB01 (Windows Server 2025, 2vCPU, 8GB) + Debian WSL2 (user: saitama)

Both share `~/.ssh/config`:

| Alias | Key | GitHub account |
|---|---|---|
| `git@github-dev` | `~/.ssh/id_ed25519` | devadalberto |
| `git@github-vertex` | `~/.ssh/vertexchaos_github_id_ed25519` | vertexchaos |
| `git@github-vertex-auto` | `~/.ssh/vertex_auto_github_id_ed25519` | vertexchaos (automation) |

**Repo:** `git@github-dev:devadalberto/backdeezup.git`  
**Identity (both machines):** `devadalberto / devadalberto@gmail.com`

**Directory layout:**
```
C:\Users\Administrator\repos\github\
  devadalberto\backdeezup          ← this repo
  orgs\vertex-chaos\freelance-launch ← git@github-vertex-auto:vertex-chaos/freelance-launch.git
  vertexchaos\vc-triage
  vertexchaos\vertexchaos-org-kit
  vertexchaos\vertexchaos-site
```

**Debian repo:** `/home/saitama/repos/github/devadalberto/backdeezup`

---

## Autostart on VM boot

```
WINWEB01 boots → Windows login
  → Startup folder: scripts/windows-autostart.bat
  → wsl -d Debian starts
  → systemd boots backdeezup.service
  → docker compose up -d (all 6 containers)
```

- **Windows:** `.bat` already in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`
- **Debian:** `backdeezup.service` enabled, `systemctl is-enabled backdeezup.service` → `enabled`
- Re-install: `sudo bash scripts/autostart.sh`

---

## CI/CD pipeline (GitHub Actions)

7 stages on every push/PR — all containerized:

```
lint+test+sast-bandit+sast-safety (parallel, in containers)
  → trivy + compose-smoke (parallel, needs lint+test)
    → playwright (needs compose-smoke)
```

| Stage | Tool | Notes |
|---|---|---|
| `lint` | ruff in python:3.12-slim | PR gate |
| `test` | Django SQLite in python:3.12-slim | PR gate |
| `sast-bandit` | Bandit → SARIF | GitHub Security tab |
| `sast-safety` | Safety dep CVEs → artifact | warn only |
| `trivy` | Trivy container scan → SARIF | warn only (exit-code 0) |
| `compose-smoke` | Full stack + HTTPS smoke | PR gate |
| `playwright` | Chromium E2E | PR gate |

---

## Deployment checklist (first deploy)

```bash
make preflight
# Set REDIS_PASSWORD in .env (not CHANGE_ME)
make gen-certs
make build && make up && make migrate && make superuser
make auth
make seed-rules && make seed-inbox-rules
make vault-setup
make gmail-discover
make gmail-loop LIMIT=500 WORKERS=10
# After download complete:
make gmail-extract-attachments
make import-media
# Visit /admin/gmail/ops/ → dry-run rules → execute
# Enable SENTRY_DSN in .env for error tracking
```

---

## Google OAuth

- **Client type:** Desktop app (`installed`) — NEVER web client
- **Client ID:** `486053539237-c454bqj13or711a74tfc8t493qlna64d` (backdeezup-desktop)
- **OAuth flow:** `make auth` → URL → browser → copy full redirect URL → paste back
- **New Google Cloud Console UI (2025+):** scopes at Google Auth Platform → Data Access; clients at Google Auth Platform → Clients
- **Photos unblock:** delete client `1ql0o9aj` → `make auth`
- **Scopes:** drive + drive.readonly + gmail.readonly + gmail.modify + `https://mail.google.com/`
- **photoslibrary.readonly** — DE-SCOPED (blocked by `1ql0o9aj`). Do NOT add back until that client is deleted.

---

## Identity groups (Gmail attachment extraction)

| Tag | Addresses |
|---|---|
| `adalberto` | jose.valdes@gmail.com + 10 variants (all Jose's accounts) |
| `monica` | mony.bello@gmail.com |
| `little-owls` | monica_littleowls@outlook.com |
| `emiliano` | virlochov@gmail.com |
| `julieta` | julietvlhr@gmail.com |

`farmaikamx`/`farferkugel`/`pelos` NOT in this inbox — separate Google account.

---

## Standing best practices (apply every session)

- **Feature branches always** — `feat/<name>`, `fix/<name>`. Never commit non-trivial changes directly to main.
- **Run `make test-full` before every merge**
- **Run `graphify update .` on Debian after structural code changes**, commit graphify-out/
- **Update shared_context.md + memory files** after every session that changes architecture/conventions
- **Security defaults:** auth=django_auth on all APIs, no `&` in onclick attrs, sanitize file paths from untrusted input, no secrets in code
- **All API endpoints require `auth=django_auth`** — no curl without CSRF; use management commands
- **Gmail download is concurrent** — `ThreadPoolExecutor(workers=10)`. Use `--workers N` to tune.
- **Drive pipeline uses management commands** — `manage.py drive_pipeline discover|download|verify`
- **Progress bars** — use periodic `\r` print, NOT tqdm (docker exec has no TTY)
- **Pydantic v2 everywhere** — `model_validate()`, no v1 adapters
- **OAuth scopes** — `mail.google.com` required for batchDelete. Token must include ALL scopes. If missing: delete token + `make auth`.
- **photoslibrary.readonly de-scoped** — do NOT add back until `1ql0o9aj` client deleted
- **HTML onclick with & params** — NEVER put URLs with & in onclick. Use named JS functions.
- **seed_rules uses gmail_query as key** — not name. Safe to re-run anytime.
- **Graphify installed:** `uv tool install graphifyy` — CLI: `~/.local/bin/graphify update .`

---

## Knowledge graph (graphify)

Current: **1268 nodes, 1732 edges, 121 communities** (post CI/CD)  
Refresh: `~/.local/bin/graphify update .` on Debian after code changes  
Read before exploring codebase: `graphify-out/GRAPH_REPORT.md`
