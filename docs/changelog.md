# Changelog

All notable changes are documented here following [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.2.0] - 2026-05-13

### Added
- **uv** package manager — Rust-based, 10-100x faster than pip, replaces manual virtualenv + pip workflow
- **pyproject.toml** — PEP 621 project configuration consolidating all dependency and build metadata
- **Developer helper scripts** — `dev.sh` (Bash) and `dev.ps1` (PowerShell) for `dev`, `migrate`, `makemigrations`, `superuser`, `shell`, `test`, `docs`, `add` commands
- **Project comparison document** — comprehensive analysis comparing BackDeezUp with a Gmail cleanup project, including feature matrix and 5-phase improvement roadmap (`docs/project-comparison.md`)
- **CHANGELOG.md** — this file, following Keep a Changelog format
- **VERSION file** — single source of truth for current version
- **Complete documentation suite** — MkDocs Material-powered docs covering quickstart, configuration, architecture, API reference, deployment, contributing, and acknowledgements
- **GitHub Actions workflow** — automated MkDocs build and deploy to GitHub Pages on every push to main

### Changed
- **Django settings** — fixed CORS/CSRF configuration for proper wildcard handling (`CORS_ALLOW_ALL_ORIGINS` used correctly, `CSRF_TRUSTED_ORIGINS` filtered)
- **README.md** — complete rewrite with working Mermaid diagrams, updated quick start, modern tooling section
- **mkdocs.yml** — full Material theme configuration with navigation tabs, search, dark/light mode, code copy
- **`DEBUG` default** changed to `True` for local development
- All **Mermaid diagrams** fixed for GitHub rendering (removed `\n` in node labels, removed non-ASCII arrows)

### Fixed
- Django system check errors: `4_0.E001` (CSRF origins) and `corsheaders.E013` (CORS origins)
- `pyproject.toml` build backend configuration to correctly locate the `backend_django` package

---

## [0.1.0] - 2026-05-12

### Added
- Initial Django project with `google_media_backup` app
- Core models: `DriveAsset`, `MediaItem`, `RunLog`
- Six-stage explicit state machine: `DISCOVERED` → `DOWNLOADED` → `IMPORTED` → `VERIFIED` → `DELETE_PENDING` → `DELETED`
- Two-proof deletion guard: file on disk + `MediaItem` DB record both required before Drive deletion
- Django-Ninja REST API with auto-generated Swagger UI at `/api/docs`
- Google Drive v3 and Google Photos Library API integration
- OAuth 2.0 authentication with Fernet-encrypted token storage
- SHA-256 deduplication: duplicate Drive files produce a single `MediaItem`
- Configurable deletion mode: `trash` (default) or `hard`
- `MIN_RETENTION_DAYS` retention guard (default: 3 days)
- Django Admin with custom ops console (`/admin/ops`)
- Docker Compose stack: web + Nginx + Postgres + Redis
- MkDocs documentation skeleton
- `graphify` knowledge graph (86 nodes, 104 edges, 24 communities)
- Multi-agent coordination via `shared_context.md`, `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`

---

[Unreleased]: https://github.com/devadalberto/backdeezup/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/devadalberto/backdeezup/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/devadalberto/backdeezup/releases/tag/v0.1.0
