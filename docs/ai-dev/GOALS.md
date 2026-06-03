/goal implement phase N  <-- type this to execute a phase

================================================================
GOAL: Back up all Google data (Gmail/Photos/Drive), serve through
      Wagtail (local SharePoint), free storage, release as FOSS.
================================================================

PHASE 0 -- Orient (DONE)
  Preflight + stack health check. Read shared_context + graph.
  Confirm all 6 containers healthy before touching anything.

PHASE 1 -- Gmail backup (DONE)
  All 32,463 messages DOWNLOADED+VERIFIED.

PHASE 2 -- Gmail sync & reconciliation (DONE)
  SOFT_DELETED state, metadata snapshots, daily reconcile task,
  90-day retention purge. DB stays in sync with Gmail reality.

PHASE 3 -- Gmail cleanup (DONE)
  16 rules executed, 11,946 messages permanently deleted from trash.
  Gmail freed from 10.71 GB → 9.78 GB. Backup guard fixed to 100%.

PHASE 4 -- Google Photos backup + delete
  Fix list_drive_files() bug. Unblock OAuth (user deletes 1ql0o9aj).
  Download all ~2,015 photos locally. Import to Wagtail vault.
  Delete from Google to free 0.43 GB.
  Make targets: photos-discover, photos-download, photos-run, photos-delete.
  Celery Beat: nightly download at 02:00 UTC.

PHASE 5 -- Drive documents backup + Wagtail library (DONE)
  480 docs discovered, 469 imported to VaultDocument.
  Google native exports (Docs→PDF, Sheets→XLSX). Served at /documents/<id>/.

PHASE 6 -- Testing suite overhaul
  pytest + strict markers (unit/integration/api/smoke).
  All external APIs mocked. No real DB for unit tests.
  Coverage ≥60%. GitHub Actions CI on every push/PR.
  Make targets: test (fast), test-full, test-cov.

PHASE 7 -- Security hardening + optimization
  /security-review on full codebase. Fix any HIGH/CRITICAL.
  Remove DEBUG=True from .env. Enforce HTTPS-only cookies.
  Audit: no secrets in git history, .env hardened, CORS locked down.
  Performance: DB indexes verified, N+1 queries fixed, static files cached.

PHASE 8 -- AI removal + merge + release
  Remove/move CLAUDE.md, AGENTS.md, GEMINI.md to docs/ai-dev/.
  Remove GOALS.md/GOALS_TODOS.md from repo root (move to docs/dev/).
  Merge feat/ci-cd-autostart into main. Tag v1.0.0.
  Verify: make test-full passes, CI green, autostart works.

PHASE 9 -- Human-operable FOSS release (FINAL)
  README: quickstart, day-to-day ops, troubleshooting (5 failure modes).
  make help lists every target. No Django/Python knowledge required.
  Celery Beat schedule documented. All scheduled tasks verified running.
  GitHub: description, topics, issues enabled, starter template.
  Claude exits. Cron and the human take over.

================================================================
TOOLS
  make preflight          -- ALWAYS run first
  make test-full          -- lint + tests (before every PR/merge)
  make photos-run         -- full Photos pipeline
  make docs-run           -- full Drive docs pipeline
  /security-review        -- before merge
  /verify                 -- live stack spot-check
  graphify update .       -- after code changes
================================================================
