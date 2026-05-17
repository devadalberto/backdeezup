# shared_context.md
> Shared ground truth for Claude, Gemini, and Codex working on this repo.
> Keep this file updated as the project evolves.
> Last updated: 2026-05-16 (v0.10.0)

---

## What this project does

**backdeezup** is a self-hosted Django platform that safely backs up Google Drive, Google Photos, and Gmail to local storage, with a provable audit trail, a two-proof deletion guard before removing anything from Drive, a Gmail cleanup rules engine, and a Wagtail CMS media vault for browsing and triaging backed-up media.

---

## Apps

| App | Purpose |
|---|---|
| `google_media_backup` | Drive/Photos pipeline — DriveAsset, MediaItem, RunLog |
| `google_gmail_backup` | Gmail pipeline + cleanup engine — GmailMessage, CleanupRule, RuleCondition, ProtectedSender, CleanupAuditLog |
| `media_vault` | Wagtail 7.4 LTS — VaultImage, VaultMedia, VaultDocument, MediaDecision |
| `core` | Landing page, HTMX stats endpoint |
| `accounts` | Custom user model — BackupUser(AbstractUser) |

---

## Pipeline status (2026-05-16)

| Pipeline | Status |
|---|---|
| Drive | 2176/2176 verified — COMPLETE |
| Gmail | ~13k/32258 verified — IN PROGRESS (gmail-loop running) |
| Photos | BLOCKED — delete old web client `1ql0o9aj` from Google Auth Platform → Clients, then `make auth` |

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 6.0+ |
| API | Django-Ninja 1.6+ (auto Swagger at `/api/docs`, `/api/gmail/docs`, `/api/vault/docs`) |
| DB prod | PostgreSQL 16 (Docker) |
| DB test | SQLite (guarded in migrations with `connection.vendor == "postgresql"`) |
| CMS | Wagtail 7.4 LTS + wagtailmedia 0.17.2 |
| Google auth | google-auth-oauthlib, Fernet-encrypted token |
| Live UI | HTMX 2.0.3 + django-htmx 1.27.0 |
| Validation | Pydantic v2 (django-ninja) |
| Scheduler | APScheduler (BACKDEEZUP_SCHEDULER=0 default) |
| Rate limiting | django-ratelimit 4.1.0 |
| Progress | tqdm (management commands) |
| Serving | Gunicorn + Nginx |
| Containers | Docker Compose: web + nginx + postgres:16 + redis:7 |
| Package manager | uv (Rust-based) |
| Config | pyproject.toml PEP 621 + python-decouple + .env |
| Theme | Matrix + Amber dark (phosphor green #00ff41 + amber #ffb300 on black) |

---

## Key URLs

| URL | Purpose |
|---|---|
| `/` | Landing page (HTMX live stats) |
| `/admin/` | Django Admin (Matrix theme) |
| `/admin/gmail/dashboard/` | Gmail dashboard — backup progress bar (HTMX 10s refresh) |
| `/admin/gmail/ops/` | Gmail ops console — pipeline, cleanup rules, empty trash |
| `/admin/gmail/rule-builder/` | Smart compound rule builder |
| `/admin/ops/` | Drive ops console |
| `/admin/reports/` | Drive reports |
| `/admin/vault/ops/` | Media Vault ops — import pipeline, review links |
| `/vault/review/` | Media review UI (K=keep D=delete S=skip Z=undo) |
| `/cms/` | Wagtail CMS |
| `/api/docs` | Drive API docs |
| `/api/gmail/docs` | Gmail API docs |
| `/api/vault/docs` | Vault API docs |

---

## Key make targets

```bash
make preflight              # ALWAYS run first — checks Docker, .env, google_client.json
make build && make up       # Build + start containers
make migrate                # Run Django migrations
make auth                   # Google OAuth (Desktop app client, headless)
make redeploy               # git pull + build + down + up + migrate
make seed-rules             # Seed 4 family protected senders + 8 cleanup rules
make vault-setup            # Create Wagtail VaultHomePage (run once)
make gmail-discover         # Discover all Gmail messages (50 pages × 500 = 25k cap)
make gmail-loop LIMIT=500   # Loop download+verify until DISCOVERED queue = 0
make gmail-progress         # Show current progress JSON
make sync-run               # Drive pipeline loop
make test-full              # lint (ruff) + 30 unit tests
```

---

## SSH / Git config

**Machine: WINWEB01** (Windows Server 2025) + **Debian WSL2** (user: saitama)

Both machines have identical `~/.ssh/config` and key files:

| SSH Host alias | Key file | GitHub account |
|---|---|---|
| `git@github-dev` | `~/.ssh/id_ed25519` | devadalberto |
| `git@github-vertex` | `~/.ssh/vertexchaos_github_id_ed25519` | vertexchaos |
| `git@github-vertex-auto` | `~/.ssh/vertex_auto_github_id_ed25519` | vertexchaos (automation) |

**Convention:** always use the SSH alias in remotes, never plain `github.com`:
```bash
# Personal repos
git remote set-url origin git@github-dev:devadalberto/<repo>.git

# Vertex org repos
git remote set-url origin git@github-vertex:vertexchaos/<repo>.git
```

**Git identity:**
- Global (both machines): `devadalberto / devadalberto@gmail.com`
- Vertex repos: set local override with `git config user.name "vertexchaos"`

**Repo directory layout on WINWEB01:**
```
C:\Users\Administrator\repos\github\
  devadalberto\backdeezup          ← this repo (git@github-dev)
  vertexchaos\vc-triage            ← needs remote set (git@github-vertex)
  vertexchaos\vertexchaos-org-kit  ← needs remote set (git@github-vertex)
  vertexchaos\vertexchaos-site     ← needs remote set (git@github-vertex)
  orgs\vertex-chaos                ← needs remote set
```

**Debian WSL repo:** `/home/saitama/repos/github/devadalberto/backdeezup`

---

## Deployment

**Docker Compose stack:** web (Gunicorn) + nginx + postgres:16 + redis:7

All credentials come from `.env` — never hardcoded. Secrets volume `./secrets:/app/backend_django/secrets:ro` mounted read-only.

**Post-deploy checklist:**
```bash
make redeploy
make seed-rules
make vault-setup          # first deploy only
# Then from /admin/gmail/ops/ apply protected senders
```

**entrypoint.sh** runs `collectstatic` then starts gunicorn.

---

## Gmail cleanup rules engine

- **ProtectedSender** — 4 family emails always starred+labeled, never trashed
- **CleanupRule** — action: TRASH / STAR / LABEL / ARCHIVE, min_age_days, enabled flag
- **RuleCondition** — compound AND/OR query builder (9 field types, 8 operators)
- **CleanupAuditLog** — immutable append-only audit trail for all rule executions
- All rules support dry_run before real execution
- Scheduler: `BACKDEEZUP_SCHEDULER=1` runs incremental sync 6h + cleanup 3×/day

---

## Media Vault

- **VaultImage** — Wagtail AbstractImage subclass, source_type/source_id tracking, keep=True/False/None
- **VaultMedia** — Wagtail AbstractMedia, video/audio, same tracking
- **MediaDecision** — audit trail for keep/delete/skip decisions
- Import pipeline: `POST /api/vault/import` or `/admin/vault/ops/` — scans verified Drive assets + Gmail attachments → VaultImage/VaultMedia (idempotent)
- Review UI at `/vault/review/` — keyboard: K=keep D=delete S=skip Z=undo

---

## Google OAuth

- **Client type MUST be Desktop app (installed)** — web clients block restricted scopes
- **Client ID:** `486053539237-c454bqj13or711a74tfc8t493qlna64d` (named `backdeezup-desktop`)
- **OAuth flow:** `make auth` → prints URL → open in browser → page fails to load → copy full URL from address bar → paste back
- **New Google Cloud Console UI (2025+):** scopes at Google Auth Platform → Data Access; clients at Google Auth Platform → Clients
- **Photos unblock:** delete old web client `1ql0o9aj` from Google Auth Platform → Clients → re-auth
- **Copying new client JSON from Downloads:** always copy the `(1).json` version (Google adds suffix when file exists)
- **Verify client type:** `python3 -c "import json; d=json.load(open('secrets/google_client.json')); print(list(d.keys())[0])"` → must print `installed`

---

## Custom user model

`accounts.BackupUser(AbstractUser)` — `AUTH_USER_MODEL = 'accounts.BackupUser'`

Migration note: `accounts/0002` uses `CREATE TABLE accounts_backupuser (LIKE auth_user INCLUDING ALL)` — PostgreSQL only. SQLite (tests) is guarded with `if schema_editor.connection.vendor == "postgresql"`.

---

## Knowledge graph (graphify)

Install: `uv tool install graphifyy` (PyPI: `graphifyy`, CLI: `graphify`)
Debian: run as `~/.local/bin/graphify update .` or add `~/.local/bin` to PATH.
Refresh after code changes: `graphify update .`
Graph output: `graphify-out/` (GRAPH_REPORT.md, wiki/index.md)
**Rule: read `graphify-out/GRAPH_REPORT.md` before reading source files.**

---

## Conventions for AI agents

- **Read `graphify-out/GRAPH_REPORT.md` first** — your map of the codebase.
- **One state transition at a time** — never skip pipeline states.
- **No mock DB in tests** — use real SQLite; we got burned by mock/prod divergence.
- **uv for all dependencies** — `uv add <package>`, never pip.
- **No comments unless WHY is non-obvious** — well-named code is self-documenting.
- **No trailing summaries** — user reads diffs, doesn't need narration.
- **Left-aligned responses** — no leading spaces.
- **vim not nano** — for any terminal editing.
- **make preflight first** — always before any deploy action.
- **SILENCED_SYSTEM_CHECKS = ["django_ratelimit.W001"]** — already in settings, don't re-add.
- **All API endpoints require `auth=django_auth`** — no curl without CSRF token; use management commands for pipeline steps instead.
- **Gmail pipeline runs as management command** — `manage.py gmail_pipeline discover|download|verify|all`, not via HTTP.
- **Progress bars in management commands** — use periodic print with `\r`, not tqdm (docker exec has no TTY).
- **Pydantic v2 everywhere** — `model_validate()` / `model_validate_json()`, no v1 adapters.
- **Private GitHub repo:** https://github.com/devadalberto/backdeezup
- **Ubuntu remote** — hostname: DTC-5CG4155DQ9, IP: 192.168.88.20, user: jose, SSH port 2222
