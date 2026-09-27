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

PHASE 4 -- Google Photos backup via Drive API (REPLANNED)
  photoslibrary.readonly scope is blocked regardless of app verification — do not chase it.
  Google Photos images are accessible via Drive API (spaces=drive) — no extra scope needed.
  Rewrite list_photos_items() and download_photos_item() to use drive_service() instead.
  Re-discover photos as drive: prefixed IDs (not photos:), clear stale photos: records.
  Download all ~3,500+ images. Import to Wagtail vault. Delete from Google to free 0.43 GB.
  No console.google.com changes required.

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
GRILL FINDINGS — quality, security, future-proofing
(items 1-15 from audit; implement in sequence after Phase 9)
================================================================

PHASE 10 -- Critical reliability fixes (grill items 1-3)
  1. OAuth token single point of failure → store in DB, health check, Sentry alert on None
  2. Celery max-retries silent failure → on_failure handler, last_error on GmailSyncState
  3. apply_rule() 5,000 cap causes incomplete execution → loop until affected_count == 0

PHASE 11 -- API hardening + index fixes (grill items 4-7)
  4. Drive export: no retry on 429/exportSizeLimit → exponential backoff, CSV fallback
  5. batchDelete idempotency → skip messages with deleted_at < 24h ago
  6. from_address ILIKE on 32k rows → add from_email_normalized field + index
  7. No rate limiting on rule execution API → Redis lock, 1 concurrent execution/account

PHASE 12 -- Performance + storage (grill items 8-9, 11, 15)
  8. Reconcile 7-hour runtime → diff Gmail list vs local DB (no per-message API calls)
  9. Double-storage of documents → hardlink or delete original after Wagtail import
  11. Container CPU/memory limits → deploy.resources.limits in docker-compose
  15. No checksum at download → verify SHA-256 vs Drive md5Checksum after download

PHASE 13 -- Schema + data integrity (grill item 10)
  10. metadata_snapshot no schema enforcement → Pydantic MetadataSnapshot, validate on write

PHASE 14 -- Multi-account + restore (grill items 12-13)
  12. Multi-account → token per email hash, pass correct token to each service call
  13. No restore-to-Gmail → restore_to_gmail() + admin action "Restore selected to Gmail"

PHASE 15 -- Webhooks + deduplication (grill items 14, 17)
  14. Polling every 6h → Gmail push webhook via Pub/Sub, 7-day watch renewal task
  17. Cross-source SHA-256 dedup → check MediaItem.sha256 before creating duplicate VaultImage

================================================================
MULTI-PROVIDER EMAIL ARCHITECTURE (v2.0 roadmap)
Supports: multiple Google accounts, Outlook, Yahoo, generic IMAP
Architecture: Provider Adapter Pattern — EmailProvider base class per provider
================================================================

PHASE 16 -- Data model: provider-aware foundation
  Rename GmailSyncState → EmailSyncState (add provider + cursor fields).
  Add unique_together (email, provider). Migrate last_history_id → cursor.
  Rename GmailMessage → EmailMessage, account_email → FK to EmailSyncState.
  Backward compatible: existing google rows keep working.

PHASE 17 -- Provider abstraction layer
  Create email_providers/ package with base.py + google.py (wraps services_gmail.py).
  google.py: thin adapter, reuses all existing service functions.
  Add outlook.py (Microsoft Graph), imap.py (stdlib imaplib, covers Yahoo + generic).
  registry.py: get_provider(sync_state) → EmailProvider dispatch.

PHASE 18 -- Parameterize Celery tasks
  All tasks accept sync_state_id param. Fan-out pattern for multiple accounts.
  Fix data leakage: reconcile + error tracking scoped per account.

PHASE 19 -- Query compiler abstraction
  Extract GmailQueryCompiler, add OutlookQueryCompiler, IMAPQueryCompiler.
  apply_rule() dispatches to provider-specific compiler.
  CleanupRule gets provider_filter field (blank = all providers).

PHASE 20 -- Multi-account OAuth + admin UI
  make auth EMAIL=user@gmail.com (existing flow, now saves email-scoped token)
  make auth EMAIL=user@outlook.com PROVIDER=outlook (new)
  Admin: provider column, per-account last_error, auth trigger action.

PHASE 21 -- FOSS multi-provider release
  README: support matrix (Gmail ✓, Outlook ✓, Yahoo ✓, IMAP ✓).
  Tag v2.0.0.

================================================================
V2 UX + TRUST UPGRADES (DONE -- source prompt cleared once implemented; see
  CHANGELOG.md for what shipped, per phase)
Goal: appliance-grade experience for non-technical users.
Rules that applied to EVERY phase below (guardrails, now historical -- see
  GOALS_TODOS.md's pointer note where the full text used to live):
  additive only; new behavior behind env/setting with default = today's behavior;
  no state-machine / two-proof-deletion changes; additive migrations only;
  one phase = one commit; make test-full green + baseline URL codes unchanged.
  Approved exceptions (2026-09-26, each with an env off-switch): 39 bind 127.0.0.1,
  41 non-root ON, 32 storage guard ON, 34 cleanup safeguards ON.
ORDER: Tracks A, B first; multi-account Phases 14, 16-20 run AFTER Track B (user decision).
Already covered elsewhere (do NOT duplicate): multi-account = Phases 14, 16-20;
  restore-to-Gmail = 14; Gmail push = 15; Redis locks / backoff / rate limit = 10-11;
  container limits = 12.
================================================================

TRACK A -- Make it usable (DONE)
PHASE 22 -- TIME_ZONE from env (default unchanged America/Los_Angeles) (DONE)
PHASE 23 -- Human-readable error mapper (utility only, no task changes) (DONE)
PHASE 24 -- System health page /health/ (read-only) (DONE)
PHASE 25 -- Unified dashboard /dashboard/ (read-only, reuses htmx_stats + progress) (DONE)
PHASE 26 -- Per-item status labels + Backup / Browse / Cleanup nav grouping (DONE)
PHASE 27 -- Dashboard action buttons (enqueue existing Celery tasks) (DONE)
PHASE 28 -- Browser-based OAuth (start, callback, scopes, reconnect, disconnect) (DONE)
PHASE 29 -- Setup wizard part 1: first-run detect, admin account, validators (DONE)
PHASE 30 -- Setup wizard part 2: services, storage, schedule, test backup (DONE)

TRACK B -- Make it trustworthy (DONE)
PHASE 31 -- Verification report + "backed up = VERIFIED" + scheduled integrity check (DONE)
PHASE 32 -- Storage warnings + disk precheck + auto-pause (guard ON by default) (DONE)
PHASE 33 -- Notifications (webhook / email / Slack / Discord, off by default) (DONE)
PHASE 34 -- Cleanup safeguards (required dry run, exact-count confirm, global pause) (DONE)
PHASE 35 -- Cleanup undo (untrash) + "protect this sender" button (DONE)
PHASE 36 -- Export to ZIP / TAR (DONE)
PHASE 37 -- Restore to local dir + conflict handling + "Can I restore?" test (DONE)
PHASE 38 -- PostgreSQL backup / restore targets + docs (DONE)

TRACK C -- Make it robust (DONE)
PHASE 39 -- Compose: web + beat healthchecks, bind 127.0.0.1 default (BIND_ADDR), config check (DONE)
PHASE 40 -- Pin uv image + .dockerignore review (DONE)
PHASE 41 -- Non-root container user (ON by default) (DONE)
PHASE 42 -- Resumable downloads + checkpointing (DONE)
PHASE 43 -- Max-concurrency setting + per-provider rate-limit knob (DONE)
PHASE 44 -- CI: vulnerability scan + SBOM (DONE)

TRACK D -- Make it distributable (docs first, packaging last) (DONE)
PHASE 45 -- README rewrite around user tasks + platform / hardware matrix (DONE)
PHASE 46 -- Disaster-recovery + upgrade guide + generated config reference (DONE)
PHASE 47 -- Prebuilt images + versioned release workflow (DONE)
PHASE 48 -- Optional Caddy HTTPS compose profile (DONE)
PHASE 49 -- One-line installer + upgrade script (DONE -- final phase of this roadmap)

NOT PHASED (backlog, needs a user decision first): restore to a different Google
account, restore into Drive, per-rule cleanup schedules, NAS packages, animated
demos, sample-Google-data test install, SBOM-signed releases.

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
