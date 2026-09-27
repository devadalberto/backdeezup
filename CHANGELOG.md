# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Phase 50** — the Phase 28 browser OAuth flow (`/dashboard/connect/start/`) was
  broken behind nginx **at any host or port**, including the documented default
  (`localhost:8445`) — not specific to any one install. `core/oauth.py` builds its
  Google redirect_uri from `request.build_absolute_uri()`, but `nginx.conf` forwarded
  `Host: $host` (nginx's `$host` strips the port) and `settings.py` never set
  `SECURE_PROXY_SSL_HEADER`/`USE_X_FORWARDED_HOST` despite nginx already sending
  `X-Forwarded-Proto: https`. Result: the redirect_uri Google received came out
  `http://<host>/...` — wrong scheme, no port — which it silently rejects after the
  user approves scopes (Google's generic "Something went wrong" page, no useful
  detail). Fixed: `nginx.conf` now sends `Host: $http_host` (preserves the port);
  `settings.py` now trusts nginx's `X-Forwarded-Proto`. Caddy (Phase 48) needed no
  change — its `reverse_proxy` already preserves the original `Host` header and sets
  `X-Forwarded-Proto`/`X-Forwarded-Host` by default. The CLI `make auth` flow was
  never affected (separate code path, no request-based redirect_uri) and was the
  working fallback while this was open. New regression test
  (`core/tests_oauth.py::test_connect_start_redirect_uri_respects_forwarded_proto_and_port`)
  — confirmed it actually catches the bug by reverting the settings.py fix and
  watching it fail (`http://` instead of `https://`) before restoring it.

### Changed
- Removed `docs/backdeezup-prompts-2026-05-19.md` (an old raw session-prompt dump,
  never referenced from anywhere) and added `*prompt*`/`*propmt*` patterns to
  `.gitignore`/`.dockerignore` so files like it don't get committed or shipped
  in the image again.
- **Phase 39** — `web` and `nginx` compose ports now bind `127.0.0.1` by default (was
  `0.0.0.0`); override with `BIND_ADDR=0.0.0.0` in `.env` to restore LAN access.
  `WEB_PORT`/`NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT` env vars added (same 8845/8844/8445
  defaults). Added `web` healthcheck (TCP probe on the gunicorn port) and `celerybeat`
  healthcheck (`pgrep` for the beat process); both were previously unmonitored.
  New `make compose-check` target (`docker compose config -q`). See `docs/deployment.md`.
- **Phase 40** — pinned the `uv` build stage from `ghcr.io/astral-sh/uv:latest` to
  `:0.12.19` (the version `:latest` resolved to as of 2026-09-27, confirmed via the
  GHCR manifest API). Added `graphify-out` and `backups` to `.dockerignore`. Verified
  with a full `docker build`: image size unchanged (1.99GB).
- **Phase 41** — the image now runs as a fixed non-root user (`appuser`, uid/gid
  `10001`) by default. `--build-arg NONROOT=0` restores the old root image. New
  `make fix-perms` target chowns the `media`/`staticfiles` volumes for existing
  installs upgrading in place (never done silently). Entrypoint now checks
  `MEDIA_ROOT` is writable before doing anything else and fails with a clear,
  `humanize_error`-derived message if not. See `docs/deployment.md`.
- **Phase 42** — Drive downloads of files >= `RESUME_MIN_MB` (default 50MB) now
  resume via HTTP Range instead of restarting from byte 0 after a dropped
  connection or a killed worker; the existing `.part`-then-atomic-rename convention
  is unchanged, so this needed no changes to any caller's error handling. Smaller
  files, and Google Docs/Sheets/Slides exports, keep the exact previous whole-file
  retry path. The weekly integrity task (Phase 31) now also removes `.part` files
  older than 7 days (never a fresh one — that's the safety margin, not a lock).
- **Phase 43** — two new soft, Redis-backed throttles on Drive downloads:
  `MAX_CONCURRENT_DOWNLOADS` (default 2, matching today's effective worker
  concurrency: `celery -c 2`) caps how many downloads run at once; `GOOGLE_API_MAX_RPS`
  (default 0, disabled) caps download calls per second. Both fail open if Redis is
  unreachable, and neither touches the existing 429/5xx exponential backoff
  (Phases 10-11). New `core/ratelimit.py`; wired into `services_google.py`'s three
  download entry points, the single choke point since Phase 42.
- **Phase 44** — CI: new `trivy-fs` job (filesystem/dependency vulnerability scan,
  SARIF, report-only) and a new SBOM step in the existing `trivy` job (`syft` via
  `anchore/sbom-action`, SPDX JSON, uploaded as the `sbom-spdx` build artifact).
  Both the new `trivy-fs` scan and the existing `trivy` image scan stay report-only
  (`exit-code: "0"`) until each has one clean run in this repo's own Actions
  history — do not flip either to fail-on-CRITICAL pre-emptively.
- **Phase 45** — rewrote `README.md` around user tasks (Install through Troubleshoot),
  with a platform matrix, an honest "no benchmarked hardware minimum" note (cites the
  compose file's actual resource limits instead), the storage-estimate formula (real
  field names from `core/storage.py`, no invented numbers), and an explicit
  backup-vs-sync-vs-archive-vs-cleanup distinction. Old terse README preserved as
  `docs/dev-quickstart.md` (now in the MkDocs nav). Fixed two stale Celery Beat
  tables in `docs/operations.md` that listed Drive/Photos/reconcile/purge tasks as
  scheduled — they aren't; only 3 tasks are ever automatic
  (`backend_django/celery_app.py` is the source of truth).
- **Phase 46** — new `docs/disaster-recovery.md` (what's recoverable, and how, for
  each of: lost server, lost `MEDIA_ROOT` only, lost database only, revoked token,
  compromised Google account) and `docs/upgrading.md` (backup-first upgrade steps,
  the non-root `fix-perms` one-timer, rolling back, diffing new `.env` vars). Both
  added to the MkDocs nav under a new "Operations" section, alongside
  `docs/operations.md` (previously missing from the nav entirely). New
  `scripts/gen_config_ref.py` walks every `config(...)` call in `backend_django/`
  and every `${VAR}` in `docker-compose.yml` via `ast`/regex and writes a generated,
  self-updating reference table into `docs/configuration.md` (`make config-ref` to
  regenerate, `make config-ref-check` to verify it isn't stale); the rest of
  `docs/configuration.md` was rewritten to match current defaults (several were
  stale — e.g. `DEBUG` defaults to `False`, not `True`) and gained a "Common
  mistakes" table. Fixed a real fresh-install bug found while writing the generated
  reference: `REDIS_PASSWORD` (required, no default in `docker-compose.yml`) was
  never added to `.env.sample`.
- **Phase 47** — new `.github/workflows/release.yml`: pushing a `vX.Y.Z` tag builds
  and pushes `ghcr.io/devadalberto/backdeezup:<tag>` (and `:latest`, for a real
  release only — never for a `-rcN` pre-release tag), gated on the repo-root
  `VERSION` file matching the tag, and creates a GitHub Release with that version's
  `CHANGELOG.md` section as its body. Release builds pin `python:3.12-slim` to a
  resolved digest via a new `PYTHON_BASE_IMAGE` Dockerfile `ARG`; `make build` is
  unaffected (unchanged floating-tag default). `docker-compose.yml`'s `web`,
  `celery`, and `celerybeat` services gained `image: ${BACKDEEZUP_IMAGE:-backdeezup:local}`
  alongside their existing `build: .` — set `BACKDEEZUP_IMAGE` in `.env` and
  `docker compose pull` to run a published image instead of building locally; unset,
  behavior is identical to before. New `docs/releases.md` documents cutting a
  release, testing the workflow with a pre-release tag, using a prebuilt image, and
  the GHCR package-visibility gotcha (a new package defaults to private). Flagged
  (not fixed — no release has actually been cut): `VERSION` (`0.10.1`),
  `pyproject.toml`'s `version` (`0.10.0`), and the newest `CHANGELOG.md` entry
  (`[0.10.0]`) don't agree with each other today.
- **Phase 48** — optional Caddy reverse-proxy profile: `docker compose --profile
  caddy up -d` (new `make caddy-up`/`make caddy-down`) starts a `caddy:2-alpine`
  service alongside nginx (which stays the default, unaffected — verified `docker
  compose config --services` lists the same 6 containers as before with no
  profile, and adds `caddy` as a 7th with `--profile caddy`). New `Caddyfile`
  mirrors nginx's two direct-serve locations (`/static/`, `/media/images/`) and
  reverse-proxies everything else to `web:8000`; defaults to `DOMAIN=localhost` +
  `CADDY_TLS_MODE=internal` (Caddy's own internal CA, same trust model as nginx's
  self-signed dev cert) so the profile works with zero config, or set a real
  `DOMAIN` + `CADDY_TLS_MODE=you@example.com` for automatic Let's Encrypt HTTPS.
  Verified live: `caddy validate` against both env combinations, and a real
  standalone run that obtained an internal-CA certificate and served HTTPS.
  `docs/deployment.md` gained a "nginx vs Caddy vs external reverse proxy"
  comparison section covering when to pick which.
- **Phase 49** — one-line installer and upgrade script, the final phase of the
  roadmap. `scripts/install.sh`: `curl -fsSL .../install.sh | bash` sets up a
  fresh install from the published image (Phase 47) with no git clone and no
  local build — fetches only what `docker compose` needs, generates
  `DJANGO_SECRET_KEY`/`GOOGLE_ENCRYPTION_KEY`/`POSTGRES_PASSWORD`/`REDIS_PASSWORD`
  locally (never printed in full), generates a self-signed cert, starts the
  stack, prints the setup-wizard URL. Prints every action; confirms before
  writing into a non-empty target or falling back to a source build if the
  image pull fails; `--dry-run` makes zero writes (verified). `scripts/upgrade.sh`
  (`make upgrade`): backup -> pull -> migrate -> up -> health-check-with-retry,
  printing exact rollback instructions (never rolling back automatically) if
  health fails; refuses to run over uncommitted changes in a git checkout.
  Both `shellcheck`-clean and verified with real `docker` runs, not just read
  for correctness.
  Two real, previously-unnoticed bugs found and fixed by that live testing,
  affecting every fresh install, not just this script: (1) `docker-compose.yml`
  declares `media` as an *external* volume that nothing in this repo ever
  created — `make up`/`make redeploy` now run `docker volume create
  backdeezup_media` first (safe to re-run); (2) `make up`/`make redeploy`
  started celery/celerybeat before running migrations, since those containers
  only wait on db/redis being healthy, not on migrations being applied —
  celerybeat crash-looped against a not-yet-migrated schema until it happened
  to retry successfully (self-healing, but confusing on first boot); fixed by
  migrating via `docker compose run --rm web ...` *before* `docker compose up
  -d` everywhere (`make up`, `make redeploy`, both new scripts, and
  `docs/upgrading.md`'s manual steps). Also fixed the Phase 41-flagged
  `accounts.0002_create_table_from_auth_user` migration, which unconditionally
  assumed a legacy `auth_user` table exists and broke `migrate` outright on any
  genuinely fresh database — now wrapped in a `to_regclass('auth_user') IS NOT
  NULL` guard so it's a no-op on a fresh install and unchanged for an upgrade
  from the legacy schema. `docs/deployment.md` gained a "One-line install"
  section; `docs/upgrading.md` gained the `make upgrade` path and the corrected
  migrate-before-up order.

## [0.10.0] - 2026-05-16

### Added
- **media_vault** Django app — Wagtail 7.4 LTS + wagtailmedia 0.17.2
  - Custom models: VaultImage, VaultDocument, VaultMedia (video/audio), VaultRendition, MediaDecision
  - All models link back to source (Drive asset or Gmail attachment)
  - `keep` field (True/False/None) on all media models for keep/delete decisions
  - Wagtail CMS admin at `/cms/`, document serve at `/documents/`, pages at `/vault/`
  - Media Vault section in top nav bar (Images, Documents, Videos & Audio)
- **Assumptions:** Django 5.2 (stable LTS) over 6.0; self-hosted video via wagtailmedia; Discord streaming deferred

## [0.9.0] - 2026-05-16

### Added
- **Smart Rule Builder** — `/admin/gmail/rule-builder/` visual compound rule editor
  - Conditions table: field, operator, value, AND/OR join per row
  - Real-time Gmail query preview (calls `/api/gmail/rule-builder/preview`)
  - Dry-run count before saving (DB-only, no Gmail API call)
  - Save as new CleanupRule with RuleCondition rows
  - 9 built-in templates: LinkedIn jobs, LinkedIn spam, job boards, recruiters, marketing tools, newsletters, no-reply, social old, promotions
- **RuleCondition model** — FK to CleanupRule, fields: field/operator/value/logic/order
  - Supports: sender, recipient, subject, body, label, category, has_attachment, age_days
  - Operators: contains, not_contains, equals, not_equals, starts_with, older_than, newer_than, is_true
- **query_compiler.py** — translates RuleCondition rows to Gmail `q=` syntax with AND/OR grouping
- **Global Matrix theme** — `backend_django/templates/admin/base_site.html` overrides Django Admin with phosphor green on black, applies to ALL admin pages
- **Top navigation bar** — sticky dropdown menus: Gmail, Drive, Pipeline, Admin
- **Export engine** — `/api/gmail/export/messages`, `/api/gmail/export/audit-log`, `/api/export/assets` supporting CSV, XLSX, JSON, XML, PDF
- **KPI dashboard** in Gmail ops console: Total messages, Verified %, Trashed, Rules active, Cleanup actions (auto-refreshes every 60s)
- **RuleCondition inline** in CleanupRule admin page

## [0.8.0] - 2026-05-15

### Added
- `ProtectedSender` model — emails from these addresses are always starred, labeled, and kept in inbox
- `CleanupRule` model — DB-backed cleanup rules with Gmail query, min_age_days, action, enabled flag
- `CleanupAuditLog` model — immutable append-only log of every cleanup action (dry-run or real)
- `services_rules.py` — rules engine: `apply_rule()`, `apply_protected_sender_rules()`, `run_all_enabled_rules()`
- `seed_rules` management command — seeds 4 protected family senders + 8 default cleanup rules (all disabled by default)
- APScheduler integration — incremental sync every 6h, protected senders every 6h, cleanup rules 3x/day at 06/12/18
- Scheduler toggle: `BACKDEEZUP_SCHEDULER=1` in `.env` (default off)
- API endpoints: `/api/gmail/rules`, `/api/gmail/rules/{id}/dry-run`, `/api/gmail/rules/{id}/execute`, `/api/gmail/rules/run-all`, `/api/gmail/protected-senders/apply`, `/api/gmail/audit-log`
- Admin: CleanupRule, ProtectedSender, CleanupAuditLog with dry-run and execute actions
- `make seed-rules` — run seed command inside container

### Protected senders seeded
- mony.bello@gmail.com, mony_littleowls@outlook.com, virlochov@gmail.com, julietvlhr@gmail.com — all starred + labeled "family"

### Default cleanup rules seeded (all disabled — review before enabling)
- Trash Promotions older than 30 days
- Trash Social notifications older than 30 days
- Trash Forums older than 60 days
- Trash Updates older than 30 days
- Trash newsletters (unsubscribe) older than 30 days
- Trash no-reply senders older than 60 days
- Trash mailing lists older than 60 days
- Trash spam folder older than 7 days

## [0.7.0] - 2026-05-15

### Added
- `GET /api/progress` endpoint — pipeline counts and percentage verified across all states
- `make sync-run` — full pipeline loop (download→import→verify) with ASCII progress bar
- `make preflight` — pre-flight checks: Docker, .env, no CHANGE_ME, google_client.json type `installed`
- `LIMIT` variable for all pipeline Makefile targets (default 100)
- graphify installed in Debian: `uv tool install graphifyy`, graph: 591 nodes, 657 edges
- `google_gmail_backup` Django app with full Gmail backup pipeline

### Fixed
- sync-run progress bar using `bash -c` to maintain function scope
- Drive query simplified (removed shortcut clause causing Google 500)
- Photos API pageSize capped at 100 (Google API limit)
- Gmail parse_date returns timezone-aware datetimes
- Gunicorn timeout increased to 300s
- OAuth: Desktop app client auto-detects redirect_uri from google_client.json
- OAuth callback URL registered in Django urls.py

### Known Issues
- Google Photos blocked project-wide — old web client has non-HTTPS redirect URIs

## [0.6.1] - 2026-05-15

### Fixed
- OAuth flow now works headless (no browser on server) — uses `urn:ietf:wg:oauth:2.0:oob` redirect, prints URL, prompts for code paste
- Gmail scopes (`gmail.readonly`, `gmail.modify`) merged into Drive/Photos SCOPES so one auth flow covers all services
- `services_gmail.py` now imports `_load_creds`, `_save_creds`, `SCOPES` from `services_google.py` (single source of truth)

### Added
- `make auth` — runs headless OAuth inside container with `-it` flag
- `docs/authentication.md` — full headless OAuth walkthrough with step-by-step instructions
- Authentication page added to MkDocs navigation

## [0.6.0] - 2026-05-15

### Added
- Comprehensive Makefile with targets for Docker, Django, Drive/Photos pipeline, Gmail pipeline, local dev, and WSL2 proxy
- `make help` shows all targets with descriptions
- `make redeploy` — one-command pull + build + restart + migrate
- `make wsl-proxy` — auto-detects WSL2 IP and sets Windows port proxy
- Pipeline targets support `HOST=` override (e.g. `make discover HOST=http://192.168.88.60:8844`)
- Updated deployment docs with full Makefile reference and Gmail pipeline steps

## [0.5.1] - 2026-05-14

### Changed
- `Dockerfile` — switched from pip + requirements.txt to uv for dependency installation; uses `ghcr.io/astral-sh/uv:latest` via COPY --from, `uv sync --frozen --no-dev`
- `requirements.txt` — regenerated from uv lockfile via `uv export`; now includes all pinned transitive deps and is always in sync with `pyproject.toml`

## [0.5.0] - 2026-05-14

### Added
- `admin_views.py` — `reports_view` (assets by state, top MIME types, totals, last 20 RunLog entries) and `ops_console` (one-click pipeline UI)
- `templates/admin/reports.html` — responsive grid dashboard with totals, state table, MIME types, recent runs
- `templates/admin/ops_console.html` — pipeline step buttons with shared limit input and live JSON output

### Fixed
- `admin.py` — removed `each_context` override that caused `RecursionError`; added `search_fields` and `readonly_fields` to all three admin classes; better action feedback messages
- `urls.py` — custom admin routes registered before `path("admin/")` (correct Django ordering); graceful `try/except` for optional `query_page` view

### Security
- Merged `dev/local-tests` branch discarding its `docker-compose.yml` (had hardcoded `app:app` credentials); main's env-var-driven version kept

## [0.4.2] - 2026-05-13

### Added
- `entrypoint.sh` — runs `collectstatic` then starts gunicorn at container start. Replaces build-time collectstatic so static files are always current.
- `secrets/.gitkeep` — ensures the secrets directory is tracked by git (contents git-ignored).
- Debian WSL2 environment: repo cloned at `/home/saitama/repos/github/devadalberto/backdeezup`.

### Changed
- `Dockerfile` — removed `COPY .env` and build-time `collectstatic`; now uses `entrypoint.sh` as CMD.
- `docker-compose.yml` — added `./secrets:/app/backend_django/secrets:ro` volume mount so OAuth credentials are injected at runtime, not baked into the image.
- `Makefile` — `migrate`, `superuser`, `shell` now run via `docker compose exec web`; `run` and `docs` remain local dev targets.
- `.env.sample` — fully updated with all current variables, inline generation commands, and `CHANGE_ME` placeholders.

## [0.4.1] - 2026-05-13

### Fixed
- `docker-compose.yml` — Postgres credentials now sourced from `.env` via `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`, `${POSTGRES_DB}`. Nothing hardcoded.
- `web` service `depends_on` upgraded to wait for db healthcheck before starting.

### Added
- README: full production deployment section with copy-paste `.env` scaffold (all secrets as `CHANGE_ME` placeholders), step-by-step deploy commands, static file notes, and ongoing ops reference.

## [0.4.0] - 2026-05-13

### Added
- **CI workflow** (`.github/workflows/ci.yml`) — runs on every push and PR to main:
  - Django system check + test suite (uv, Python 3.12, sqlite)
  - Playwright smoke test: confirms Swagger UI and Admin login load on localhost:8844
  - Uses `astral-sh/setup-uv` for fast dependency install
- **Playwright 1.59** added as a project dependency — headless Chromium installed and smoke-tested on WINWEB01

### Fixed
- All remaining broken Mermaid diagrams in `shared_context.md` — removed `\n` in node labels and Unicode arrows
- `gh-pages.yml` — added `enablement: true` to `configure-pages` step to auto-enable GitHub Pages (fixes all prior deploy failures)

### Changed
- `shared_context.md` — updated Playwright status to installed/working, added CI workflow reference, noted GitHub Pages manual activation requirement, corrected WSL status

## [0.3.0] - 2026-05-13

### Added
- Complete MkDocs Material documentation site with 10 pages: index, quickstart, configuration, installation, architecture, states, data model, API reference, deployment, contributing, changelog, acknowledgements
- Working Mermaid diagrams throughout docs and README (fixed for GitHub rendering)
- GitHub Actions workflow with separate build/deploy jobs and proper environment gating

### Changed
- All Mermaid diagrams: removed `\n` in node labels and transition text (broke GitHub renderer), removed non-ASCII arrows and checkmarks
- `mkdocs.yml`: renamed from `gmail_josevaldes_cleanup`, full Material theme config with dark/light mode, nav tabs, search, code copy
- `docs/handover.md`: fixed all Mermaid diagrams
- README: complete rewrite with working diagrams and modern quick start

## [0.2.0] - 2026-05-13

### Added
- **Modern Python tooling**: Migrated to `uv` (Rust-based package manager) for 10-100x faster dependency management
- **pyproject.toml**: Consolidated all dependencies and project metadata in PEP 621 format
- **Developer scripts**: Added `dev.sh` (Bash) and `dev.ps1` (PowerShell) helper scripts for common Django tasks
  - Commands: `dev`, `migrate`, `makemigrations`, `superuser`, `shell`, `test`, `docs`, `sync`, `add`
- **Project comparison document**: Comprehensive analysis comparing BackDeezUp with Gmail cleanup project (`docs/project-comparison.md`)
  - Feature matrix comparing 30+ dimensions
  - Detailed improvement roadmap to blend best features of both projects
  - Migration path for future enhancements (multi-account, cleanup rules, reporting, exports)
- **CHANGELOG.md**: This changelog following Keep a Changelog format with semantic versioning

### Changed
- **Django settings**: Fixed CORS and CSRF configuration to properly handle wildcard origins
  - `CORS_ALLOW_ALL_ORIGINS` now used instead of invalid `*` in origins list
  - `CSRF_TRUSTED_ORIGINS` properly filtered for non-wildcard values
  - `DEBUG` default changed to `True` for development
- **README.md**: Updated with modern uv-based workflow
  - Added uv quick start guide
  - Documented new development scripts
  - Highlighted modern tooling benefits (10-100x faster, automatic venv management, lock files)
  - Added note about legacy Makefile targets

### Fixed
- Django system check errors for CORS/CSRF configuration (4_0.E001, corsheaders.E013)
- Build backend configuration in pyproject.toml to recognize `backend_django` package

### Technical
- Dependencies locked in `uv.lock` for reproducible builds
- Virtual environment automatically managed by uv (`.venv/`)
- Build backend: Hatchling with proper package configuration

## [0.1.0] - 2026-05-12

### Added
- Initial Django project structure with `google_media_backup` app
- Google Drive and Photos API integration with OAuth authentication
- Core models: `MediaItem`, `DriveAsset`, `RunLog`
- Explicit 6-stage state machine: DISCOVERED → DOWNLOADED → IMPORTED → VERIFIED → DELETE_PENDING → DELETED
- Two-proof deletion safety: File exists on disk + DB record required before Drive deletion
- Django-Ninja REST API with Swagger/OpenAPI documentation at `/api/docs`
- SHA-256 hashing for media deduplication
- Fernet-encrypted token storage for OAuth credentials
- Docker Compose setup with PostgreSQL and Nginx
- MkDocs documentation site
- Makefile with common development tasks
- Knowledge graph via graphify (86 nodes, 104 edges, 24 communities)
- CLAUDE.md and GEMINI.md for AI agent collaboration

### Safety Features
- MIN_RETENTION_DAYS guard (default: 3 days) before Drive deletion
- Configurable deletion mode: trash (recoverable) or hard (permanent)
- State-based pipeline ensures no premature deletions
- Audit trail via RunLog model

[Unreleased]: https://github.com/devadalberto/backdeezup/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/devadalberto/backdeezup/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/devadalberto/backdeezup/releases/tag/v0.1.0
