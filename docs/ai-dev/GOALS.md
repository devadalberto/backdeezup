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

================================================================
BUGS FOUND POST-ROADMAP (not part of the original V2 plan)
================================================================
PHASE 50 -- Fix OAuth redirect_uri behind reverse proxy (browser flow) (DONE)
PHASE 51 -- Fix gmail-loop infinite-retry on permanently-gone messages (DONE)
PHASE 52 -- Fix NOT NULL crash on every successful Gmail download/verify (DONE)
  Found 2026-09-27/28 on the same real account, right after Phase 51 confirmed working
  (152 messages correctly cleared). 348 OTHER messages stuck in DISCOVERED with a
  genuinely different error: `null value in column "error" ... violates not-null
  constraint`. Root cause confirmed by reading the model + all 4 call sites (not
  guessed): `GmailMessage.error = models.TextField(blank=True, default="")` has no
  `null=True` -- `blank=True` only affects form validation, the real Postgres column
  is NOT NULL. `gmail_pipeline.py`'s download success path (line 144) AND verify
  success path (line 208), plus the duplicate HTTP-API equivalents in `api.py` (lines
  270, 302), all set `msg.error = None` on success -- crashes `.save()` every time,
  on Postgres AND SQLite alike (verified while fixing -- not a SQLite-vs-Postgres
  gap). Never caught before because no existing test ever ran the actual
  download/verify success path with real data (the one test that did always used
  an empty queue, dodging a separate ThreadPoolExecutor/TestCase deadlock issue).
  Effect: once a message's download/verify actually
  succeeds, the final state-saving .save() crashes trying to write error=None -- the
  file is already on disk, but the row never advances past DISCOVERED/DOWNLOADED and
  gets retried forever. NOTE: thousands of pre-existing DOWNLOADED/VERIFIED rows exist
  in this same database from earlier (Phase 1 era, mid-2026) -- so this exact crash
  either wasn't always present (something changed since then) or those earlier runs
  went through a different code path; not fully explained yet, don't assume this has
  ALWAYS been 100% broken, just that it demonstrably is right now.
  Found 2026-09-27 on a real account (57,895 discovered messages): `_download()` in
  gmail_pipeline.py never transitions GmailMessage.state on failure -- only sets
  error/last_attempt_at. A message Gmail confirms is gone (404/notFound on
  messages.get) stays DISCOVERED forever, and since the download query is
  `filter(state=DISCOVERED).order_by("discovered_at")[:limit]`, the same oldest
  dead messages get re-selected on every loop pass -- `make gmail-loop`'s "loop
  until DISCOVERED queue is empty" can never make forward progress past them.
  Reproduced live: 500/500 failed, all 404, loop stuck. task_gmail_reconcile
  already handles this exact signal correctly (marks SOFT_DELETED) but only scans
  VERIFIED/DOWNLOADED messages, not DISCOVERED ones -- doesn't help here.
  Found 2026-09-27 debugging a real install (PDX-CL1): the Phase 28 browser OAuth
  flow fails universally behind nginx (any host, any port, not specific to that
  machine) -- Google shows a generic "Something went wrong" after the user approves
  scopes. `core/oauth.py` builds redirect_uri from `request.build_absolute_uri()`,
  but nginx forwards `Host: $host` (strips the port) and Django has no
  SECURE_PROXY_SSL_HEADER/USE_X_FORWARDED_HOST configured despite nginx sending
  X-Forwarded-Proto: https -- so the redirect_uri sent to Google ends up wrong
  scheme (http) and missing the port entirely. The CLI `make auth` flow is
  unaffected (different code path, no request-based redirect_uri) and is the
  working fallback until this lands.

================================================================
POST-ROADMAP ENHANCEMENTS (not bugs -- optional tuning)
================================================================
PHASE 53 -- Configurable concurrency + resource limits for bigger hardware (DONE)
  User is moving PDX-CL1 to a 12-vCPU/36GB VM and asked how to size gmail-loop
  workers for it. Today's answer is capped by three HARDCODED values in
  docker-compose.yml, none read from .env: celery worker `-c 2` (this governs
  how many Celery TASKS run in parallel -- reconcile/verify/media -- not the
  ThreadPoolExecutor inside a single gmail-loop batch task, which already
  takes WORKERS=N via `make gmail-loop`), and cpu/memory deploy.resources.limits
  on web (1.0/512M), celery (2.0/1G), celerybeat (0.25/192M). Gmail downloads
  are I/O-bound (network + hash + DB save, confirmed by reading
  gmail_pipeline.py's _process() -- nothing CPU-heavy), so the real ceiling on
  worker count is Gmail's per-user API quota, not vCPU count -- going far past
  ~15-20 threads mostly trades throughput for 429s. `MAX_CONCURRENT_DOWNLOADS`
  (default 2) only gates Drive/media downloads today, not Gmail -- confirmed
  by grep. Fix: make the three hardcoded values env-driven with today's exact
  values as defaults (zero behavior change), add a hardware-sizing table to
  docs/operations.md so this doesn't need to be answered ad hoc again. No
  application code changes, no migrations. Full detail: GOALS_TODOS.md.

PHASE 54 -- Apply Phase 51's 404-permanent-gone fix to api.py's /sync/download (DONE)
  `google_gmail_backup/api.py`'s HTTP-triggered download endpoint (lines 236-283)
  has the same Phase-51-shaped bug -- its `except Exception as e:` block
  (lines 277-281) unconditionally sets `error` with no 404/permanent-gone check,
  so a confirmed-gone message can still get stuck here the way `gmail_pipeline.py`'s
  download did before Phase 51. Not fixed in Phase 52 (out of scope -- that phase
  only touched the `error = None` NOT NULL issue) -- noticed while reading the
  surrounding code, now confirmed by reading it again in full.
  Fix mirrors Phase 51 exactly: `HttpError` is already imported at api.py:10
  (module level, no new import needed). `_mark_soft_deleted` (tasks.py:357-369)
  is confirmed importable from api.py with no circular dependency (api.py doesn't
  import from tasks.py at module level; tasks.py only imports `.models`/`.schemas`).
  Add the same `is_gone` check gmail_pipeline.py uses (`isinstance(e, HttpError)
  and e.resp.status == 404`, or `"404"`/`"notFound"` string fallback) to the
  except block; on a confirmed-gone message call `_mark_soft_deleted(msg.gmail_id,
  "gmail_404_on_download", timezone.now())` instead of just setting `error`.
  Check gmail_pipeline.py's exact `errors` counter behavior on the soft-deleted
  branch before mirroring it here, so the two endpoints report progress
  consistently. Full detail: GOALS_TODOS.md.

PHASE 55 -- Fix broken CI (lint, sast-bandit, test jobs all failing)
  Surfaced when the CI badge was added to README; confirmed still failing on
  current HEAD (commit 7a9a275, run 36363155626, inspected via `gh run view
  --log-failed`) -- not a flake, three independent root causes:
    1. lint -- 25 real `F401` unused-import violations across the codebase
       (e.g. `core.setup.views` in tests_setup_wizard2.py:15, `django.utils.timezone`
       in google_gmail_backup/admin.py:94, several unused model imports in
       tests_smoke.py). Auto-fixable: `ruff check backend_django/ --select E,F,W
       --ignore E501,E701,E702 --fix`.
    2. sast-bandit -- FIXED (confirmed root cause, 2026-09-27). `bandit.sarif`
       came out malformed/truncated ("Invalid SARIF. JSON syntax error:
       Unexpected end of JSON input") at the upload-sarif step. Confirmed via
       the "Run Bandit SAST" step's own output (not the upload step): bandit
       itself errors out ("unrecognized arguments: backend_django/core/migrations
       ..."), because `-x backend_django/**/migrations` is unquoted in the
       workflow -- the runner's `sh` glob-expands `**` into 4 separate paths
       before bandit sees them, only the first is consumed by `-x`, the rest
       become invalid positional args, bandit exits nonzero, `|| true` hides it,
       and `bandit.sarif` never gets written. Not the suspected zero-findings
       SARIF-formatter bug -- disproven; quoting alone fixes it and findings
       are non-zero (22 at `--severity-level medium`). Fix: quote the value --
       `-x "backend_django/**/migrations"` -- verified locally with
       `uv tool run --with 'bandit[sarif]' bandit ...` against this exact repo
       (valid JSON, 22 results, zero touching migrations).
    3. test -- exit 137 (OOM-killed) on the `test` job's container, AND 6 test
       modules fail to even import as `_FailedTest`: google_media_backup's
       tests_resumable_download + tests_unit, google_gmail_backup's
       tests_cleanup_safeguards + tests_notify_wiring + tests_schemas +
       tests_undo_protect. Partially diagnosed 2026-09-27: the `_FailedTest`
       placeholders are emitted at discovery time, but their real tracebacks
       only print in unittest's end-of-run summary, which this run never
       reaches because the OOM kill happens first -- so the traceback text is
       unobtainable from any existing CI log. A scoped local run of exactly
       those 6 modules together passes cleanly (exit 0), so the failure isn't
       intrinsic to those files alone -- it only shows up as part of the full
       two-app suite. The raw log also shows a second, unexplained
       `wagtailusers.0015` migration-apply appearing mid-suite (only one test
       DB is ever created), right before the kill -- a lead pointing at
       something re-triggering DB setup mid-run, not a confirmed cause.
       Getting the real evidence needs a run that survives to print the
       summary (i.e., more memory / a run on PDX-CL1) -- this repo's local dev
       box cannot safely run the full two-app suite (WSL) and can't reach
       Google Drive/Gmail anyway, so this step's remaining diagnosis and fix
       happen on PDX-CL1, not here.
  Full detail + required diagnostic steps before each fix: GOALS_TODOS.md.

PHASE 56 -- Fix `make gmail-loop` ignoring WORKERS= (XS) (DONE)
  Confirmed live: user set a bigger `WORKERS=` value (12-vCPU/36GB VM, Phase 53
  follow-up) and `gmail-loop` kept using 10. Root cause confirmed by reading the
  code, not guessed: `make gmail-download` correctly passes `--workers $(WORKERS)`
  to `gmail_pipeline download` (Makefile:407), but `gmail-loop`'s own download
  call (Makefile:424) never forwards `--workers` at all, so it silently falls
  back to the management command's own hardcoded `default=10`
  (`gmail_pipeline.py:23`) no matter what `WORKERS=` is set to on the command
  line. `gmail-loop`'s `verify` call has no `--workers` flag to begin with (not
  a bug -- `verify` doesn't take one, confirmed by reading its `add_arguments`).
  Fix: add `--workers $(WORKERS)` to `gmail-loop`'s download line, matching
  `gmail-download` exactly. One line, no behavior change for anyone who doesn't
  override `WORKERS=` (still defaults to 10). Full detail: GOALS_TODOS.md.

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
