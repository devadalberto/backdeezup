# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
