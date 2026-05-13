# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
