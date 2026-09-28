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

PHASE 55 -- Fix broken CI (lint, sast-bandit, test jobs all failing) (DONE -- via PHASES 57 + 63)
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
       MAJOR FINDING 2026-09-28 (confirmed live on PDX-CL1): with `DATABASE_URL=`
       cleared to force the SQLite path, the run got past everything CI ever
       showed and hung indefinitely (not crashed) at `ProtectedSenderReconcileTest
       .test_protected_sender_still_soft_deleted_on_404` -- a genuine infinite
       loop, verified by reproducing `MagicMock()` pagination behavior in an
       isolated shell: `task_gmail_reconcile()` paginates on `res.get("nextPageToken")`,
       but this test (and 3 siblings in the same file) mock `svc` without
       configuring `.list()`, so that call returns a permanently-truthy `MagicMock`
       and the loop never breaks -- a very plausible match for the OOM (no sleep,
       unbounded `mock_calls` growth per iteration). Not a production bug. Fixed: PHASE 57.
       ROOT CAUSE CONFIRMED 2026-09-28 (after Phase 57 deployed): a full local run
       on PDX-CL1 (`DATABASE_URL=` cleared) now completes cleanly in 5s -- "Ran 74
       tests ... OK (skipped=2)" -- confirming Phase 57's infinite loop was the
       entire OOM story. But CI's own run on this same commit still fails the
       `test` job (`gh run 36452103678`), now FAST (45s, no OOM) with real
       tracebacks finally visible (the OOM used to prevent them from ever
       printing): all 6 modules fail with the identical `ModuleNotFoundError: No
       module named 'pytest'`. Confirmed by reading each file: all 6 are genuine
       pytest-native tests (`@pytest.mark.django_db`, `@pytest.fixture`,
       `@pytest.mark.unit`, `tmp_path`/`monkeypatch` fixtures) -- not
       unittest.TestCase-based like the rest of the codebase. `pyproject.toml`
       already has a fully-configured `[tool.pytest.ini_options]` section and a
       declared `test` optional-dependency group (`pytest`, `pytest-django`,
       `pytest-cov`, `pytest-mock`) -- but CI's `test` job's `uv sync` (no
       `--extra test`) never installs it, and CI never runs `pytest` at all.
       These 6 files have likely never actually executed in CI, ever. Verified
       locally: `uv sync --extra test` + `uv run pytest <the 6 files> -v` --
       65 passed, 0 failed, 7.69s. Fix: PHASE 63.
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

PHASE 57 -- Fix infinite loop in 4 task_gmail_reconcile tests (under-mocked `.list()`) (XS-S) (DONE)
  Found live on PDX-CL1 while diagnosing Phase 55 Step 3's OOM: with
  `DATABASE_URL=` cleared (SQLite, matching CI), the full test run hung
  indefinitely at `ProtectedSenderReconcileTest
  .test_protected_sender_still_soft_deleted_on_404`. Confirmed root cause:
  `task_gmail_reconcile()` (`tasks.py:283-293`) paginates via
  `page_token = res.get("nextPageToken"); if not page_token: break`, but 4
  tests in `tests_reconciliation.py` (`Reconcile404Test`, `ReconcileTrashLabelTest`,
  `ReconcileMessageAliveTest`, `ProtectedSenderReconcileTest`) mock `svc` as a
  bare `MagicMock()` without configuring `.list()` -- verified empirically that
  `MagicMock().get("nextPageToken")` returns a permanently-truthy `MagicMock`,
  so the loop never terminates. No production bug (real API responses are real
  dicts). Fix: configure `.list()`'s return value (`{"messages": [],
  "nextPageToken": None}`) in each of the 4 tests before calling
  `task_gmail_reconcile()`. Test-only change. Full detail: GOALS_TODOS.md.

PHASE 58 -- Fix nginx's HTTP->HTTPS redirect hardcoding port 8445 (S) (DONE)
  Found live on PDX-CL1: its `docker ps` shows nginx published on
  `127.0.0.1:18844->80/tcp, 127.0.0.1:18445->443/tcp` (customized via
  `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT` in its `.env`), but `nginx/nginx.conf:13`'s
  redirect is `return 301 https://$host:8445$request_uri;` -- a literal `8445`,
  not driven by any variable. `docker-compose.yml:122` bind-mounts
  `nginx.conf` as a static, unmodified file (`./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`)
  -- no substitution happens on it at all, even though `docker-compose.yml:127-128`
  DOES correctly read `NGINX_HTTPS_PORT` for the port mapping itself. Confirmed
  impact: anyone hitting PDX-CL1's `http://<host>:18844/` gets redirected to
  `https://<host>:8445/...`, a port nginx isn't even listening on for this
  deployment (not in its published ports at all) -- the request just fails.
  Docker's port remapping is transparent to the container, so nginx has no way
  to know the externally-published HTTPS port without being told explicitly --
  no nginx-variable trick (`$server_port`, `$http_host`, etc.) can substitute
  for this, since HTTP and HTTPS use *different* custom host ports here.
  Fix: make `nginx.conf` a template that reads `NGINX_HTTPS_PORT` at container
  start, since the official nginx image's built-in template auto-processing
  (`/etc/nginx/templates/*.template` -> `/etc/nginx/conf.d/*.conf`) doesn't fit
  our case -- we replace the *entire* nginx.conf (worker_processes/events/http
  wrapper), not a conf.d fragment. Instead: rename `nginx/nginx.conf` ->
  `nginx/nginx.conf.template` (hardcoded `8445` -> `${NGINX_HTTPS_PORT}`), mount
  the template instead of the static file, pass `NGINX_HTTPS_PORT` as an env var
  to the nginx service, and override its `command` to run `envsubst` before
  starting nginx:
      command: ["/bin/sh", "-c", "envsubst '$$NGINX_HTTPS_PORT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
  (the `$$` escapes docker-compose's own interpolation so the shell/envsubst
  sees a literal `$NGINX_HTTPS_PORT`). Default unchanged (`8445`) for anyone
  not overriding it. Verify: `docker compose config` shows the new command/env,
  then start the stack and confirm `curl -I http://localhost:$NGINX_HTTP_PORT/`
  redirects to the *actual* published `NGINX_HTTPS_PORT`, not 8445 -- test both
  the default and a custom-port override. Full detail: GOALS_TODOS.md.

PHASE 59 -- Fix Makefile ops commands hardcoding port 8844/8845 (ignoring custom ports) (S) (DONE)
  Found live on PDX-CL1 (same deployment, right after Phase 58's port fix):
  `make gmail-progress` failed with `python3 -m json.tool`'s confusing
  "Expecting value: line 1 column 1 (char 0)" -- traced to `curl -s` silently
  returning zero bytes because it hit the WRONG, unbound port.

  Facts confirmed by reading the Makefile (not guessed):
    - `HOST ?= http://localhost:8844` (Makefile:292) -- hardcoded, doesn't read
      `.env`'s `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT`. 9 targets use `$(HOST)` in
      a curl call: `progress`, `sync-download`, `sync-run` (3 calls inline),
      `sync-import`, `sync-verify`, `sync-mark-delete`, `sync-commit-delete`,
      `gmail-incremental`, `gmail-progress`.
    - None of those curl calls pass `-S` (only `-s`), so a real connection
      failure produces zero output with NO error message -- confirmed this is
      exactly what happened on PDX-CL1 (port 8844 isn't published on this
      deployment at all; nothing in its `docker ps` output listens there).
    - `check-services` (Makefile:204,212) hardcodes literal ports `8845`/`8844`
      directly (not even via a variable) for its own port-bound/HTTP-response
      diagnostic checks -- same gap, worse (no override possible at all today).
    - This is the THIRD recurrence of the same pattern this session: Phase 56
      (`gmail-loop` ignoring `WORKERS=`), Phase 58 (nginx hardcoding the
      redirect port), now the ops-command layer.
    - `HOST`'s default is plain `http://`, matching `make run`'s bare dev
      server (no nginx, no TLS) -- but the actual docker-compose deployment
      fronts everything through nginx with a self-signed cert (Phase 58's
      redirect goes exactly there), so hitting the HTTP port on a real
      deployment costs an extra redirect hop `curl` won't follow without `-L`,
      and the HTTPS endpoint needs `-k` for the self-signed cert (already the
      documented convention elsewhere -- `docs/api.md`/`URL_INDEX.md` both
      say `curl -k https://localhost:8445/...`).

  Fix:
    1. Compute `HOST` once, at Makefile-parse time, from `.env` if present,
       falling back to today's defaults if not (so a plain git checkout with
       no `.env` yet, or the standard un-customized install, behaves exactly
       as today):
         NGINX_HTTPS_PORT := $(shell grep -E '^NGINX_HTTPS_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2)
         NGINX_HTTPS_PORT := $(if $(NGINX_HTTPS_PORT),$(NGINX_HTTPS_PORT),8445)
         HOST ?= https://localhost:$(NGINX_HTTPS_PORT)
       (Switches the default scheme from `http` to `https` -- going straight
       to the real endpoint instead of relying on an unfollowed redirect.
       `WORKERS=`/`LIMIT=`-style override still works: `make gmail-progress
       HOST=...` continues to take precedence via `?=`.)
    2. Add `-k` to every one of the 9 `$(HOST)`-using curl calls (matches the
       project's own documented convention for hitting this self-signed-cert
       endpoint elsewhere), and change `-s` to `-sS` on all of them so a real
       failure prints curl's actual error instead of silently feeding
       `json.tool` zero bytes.
    3. `check-services`: replace the hardcoded `8845`/`8844` literals with the
       same `.env`-read pattern (`WEB_PORT`/`NGINX_HTTP_PORT`, defaults
       unchanged), so its own diagnostic actually checks the ports this
       deployment is really using.
    4. `docs/operations.md`: add a short note that these ops commands
       auto-detect `.env`'s ports, so a customized deployment doesn't need
       manual `HOST=` overrides for routine use.

  Verify: `make -n gmail-progress` (dry-run) with no `.env` present shows the
  unchanged default `https://localhost:8445` (behavior-preserving check, since
  `.env` doesn't exist in this git checkout); construct a throwaway `.env`
  with `NGINX_HTTPS_PORT=18445` and confirm the same dry-run now shows
  `https://localhost:18445` -- delete the throwaway `.env` after. Full
  end-to-end proof (an actual working `make gmail-progress` against a real
  custom-port deployment) needs to happen on PDX-CL1, same as Phase 58.
  Full detail: GOALS_TODOS.md.

PHASE 60 -- Fix tqdm crash breaking cleanup-dry, cleanup-run, and real empty-trash (S) (DONE)
  Found live: `make cleanup-dry` crashed immediately with `TypeError: string
  indices must be integers, not 'str'`. Confirmed root cause by reproducing
  the exact error in an isolated Python shell (not guessed) and empirically
  verifying the fix before writing any code.

  Facts confirmed:
    - `run_cleanup.py` and `empty_gmail_trash.py` both build a custom tqdm
      `bar_format` referencing `{postfix[msgs]}` / `{postfix[d]}` -- treating
      `postfix` as if it stays a subscriptable dict inside the format string.
      It doesn't: tqdm converts `postfix` to a plain string (e.g. `"msgs=42"`)
      the moment it's used for display -- confirmed via `pbar.format_dict['postfix']`
      returning a str, not a dict. `"msgs=42"["msgs"]` -> exactly the observed
      `TypeError`. This crashes on the VERY FIRST `tqdm(...)` construction
      (inside its own initial `refresh()`), before the loop body ever runs.
    - There's a SECOND, latent bug the obvious one-line fix would walk
      straight into: both files also do `pbar.postfix["msgs"] = value` /
      `pbar.postfix["d"] = value` mid-loop, mutating `pbar.postfix` as if it
      stays a dict -- but it's already been converted to a string by the
      first `refresh()`, so this ALSO raises (`'str' object does not support
      item assignment`), confirmed by reproducing this second error too,
      separately, before finalizing the fix.
    - Impact, confirmed live: `make cleanup-dry` and `make cleanup-run` (both
      go through `run_cleanup.py`) are completely, unconditionally broken --
      100% reproducible, not intermittent. `make gmail-empty-trash-dry` is
      NOT affected (it returns early, before ever reaching the tqdm block,
      confirmed by reading `empty_gmail_trash.py`'s control flow) -- but the
      REAL execution path (`make gmail-empty-trash`, once `--confirm`'d) goes
      straight through the same broken tqdm block and would crash too,
      confirmed by reading the code (not yet triggered live, since the user
      hasn't run the real delete yet).
    - This blocks the exact next thing the user is trying to do: dry-run then
      execute the newly-seeded 20 cleanup rules, and eventually empty the
      already-8976-message Gmail trash for real.

  Fix (verified empirically in an isolated shell before writing the code):
    - `bar_format`: replace `{postfix[msgs]}` / `{postfix[d]}` with plain
      `{postfix}` (drop the redundant literal `msgs=`/`deleted=` text --
      tqdm's own postfix string already includes the key name, e.g. `"msgs=42"`).
    - Mid-loop update: replace `pbar.postfix["msgs"] = value; pbar.set_postfix(pbar.postfix)`
      with the correct keyword-argument API, `pbar.set_postfix(msgs=value)`
      (same for `empty_gmail_trash.py`'s `d` key). Verified this exact
      corrected pattern runs a full loop with no exception.
    - Also drop the now-redundant `postfix={"msgs": 0}` / `postfix={"d": 0}`
      constructor kwarg (no longer needed once `bar_format` doesn't reference
      it before the first `set_postfix()` call).

  Verify: `make cleanup-dry` completes without a traceback and prints real
  per-rule affected counts (confirms both `run_cleanup.py`'s tqdm bugs are
  actually fixed, not just the constructor-time one). Since the real delete
  path in `empty_gmail_trash.py` can't be safely tested here (irreversible,
  real Gmail data, no live stack on this dev box), verify that one by reading
  the corrected code against the same pattern already proven fixed in
  `run_cleanup.py`, and let the user confirm on PDX-CL1 when they actually
  run `make gmail-empty-trash` for real. Full detail: GOALS_TODOS.md.

PHASE 61 -- Fix ops console Output panel: not collapsible, grows unbounded and drags the page (XS-S) (DONE)
  Found live on `/admin/gmail/ops/`: the "▶ Output" header is a static
  unicode glyph inside a plain `<b>` tag -- no `onclick`, no `<details>`/
  `<summary>`, confirmed by grepping the whole file (zero matches for
  "details"/"summary"). Looks clickable, does nothing. Separately, `<pre
  id="out">` has no `max-height`/`overflow`, and its container is
  `position:sticky` -- so as output grows (e.g. a 20-rule dry-run's JSON),
  the box's own height grows unbounded and, being sticky, visibly drags the
  page around. Fix: replace the static `<b>` with a real `<details open>`/
  `<summary>` (native, accessible, free expand/collapse triangle, no JS
  needed) and add `max-height:320px;overflow-y:auto;` to `<pre id="out">` so
  long output scrolls within its own fixed box instead of growing the
  sticky container. Template-only, no backend change. Full detail: GOALS_TODOS.md.

PHASE 62 -- Fix django_ratelimit's Ratelimited returning raw Django 403 instead of clean JSON (XS-S) (DONE)
  Found live: clicking "Execute" on a cleanup rule returned a raw, unstyled
  "403 Forbidden" page with no explanation. Confirmed byte-for-byte this is
  Django's own generic `permission_denied` fallback page (rendered locally
  and compared character-for-character) -- meaning `django_ratelimit`'s
  `Ratelimited` exception (a `PermissionDenied` subclass, raised by the 4
  `@ratelimit(...)`-decorated endpoints in `api.py`, all on `gmail_api`) is
  unhandled by Ninja and falls through to Django's default error handling
  instead of a clean JSON response. Very likely the user genuinely hit the
  `10/h` execute limit (or `3/h` run-all limit) from extensive testing this
  session -- the rate limit itself is a reasonable safety feature; the bug
  is purely the broken error presentation. Fix: register one
  `@gmail_api.exception_handler(Ratelimited)` returning a clean `429` JSON
  body (`{"error": "Rate limit exceeded. Please wait before trying again."}`)
  -- covers all 4 rate-limited endpoints at once. Verified working end-to-end
  with `ninja.testing.TestClient` against a throwaway API instance before
  writing the real code. Full detail: GOALS_TODOS.md.

PHASE 63 -- Wire pytest into CI so it actually runs the 6 pytest-native test files (S) (DONE)
  Completes Phase 55: the `test` job's real remaining failure
  (`ModuleNotFoundError: No module named 'pytest'` on 6 files) is fully
  diagnosed -- these are genuine pytest-native tests (fixtures, `django_db`/
  `unit` markers) that `pyproject.toml` already declares a `test` optional-
  dependency group for (`pytest`, `pytest-django`, `pytest-cov`,
  `pytest-mock`) and a full `[tool.pytest.ini_options]` config for -- but
  CI's `test` job's `uv sync` never installs that group, and CI never
  invokes `pytest` at all. These 6 files have likely never actually run in
  CI. Verified locally: `uv sync --extra test` + `uv run pytest <the 6
  files> -v` -> 65 passed, 0 failed, 7.69s.
  Fix: in `.github/workflows/ci.yml`'s `test` job, change `uv sync` ->
  `uv sync --extra test`, and add one more step after the existing
  `manage.py test` step, running `pytest` scoped to exactly the 6 files
  (not a bare `pytest` across `backend_django/` -- that would also
  re-collect and re-run every unittest.TestCase-based file `manage.py test`
  already covers, doubling CI time for no benefit):
      - name: Run tests (pytest-native)
        run: |
          uv run pytest \
            backend_django/google_media_backup/tests_resumable_download.py \
            backend_django/google_media_backup/tests_unit.py \
            backend_django/google_gmail_backup/tests_cleanup_safeguards.py \
            backend_django/google_gmail_backup/tests_notify_wiring.py \
            backend_django/google_gmail_backup/tests_schemas.py \
            backend_django/google_gmail_backup/tests_undo_protect.py \
            -v
  The workflow-level `env:` block (DJANGO_SECRET_KEY, DATABASE_URL: "", etc.,
  lines 9-13) already applies to every step in every job -- no new env vars
  needed for this step.
  Verify: `gh run list --workflow=ci.yml --limit 1` shows a fully green run
  (lint, sast-bandit, AND test all passing) on the commit carrying this fix
  -- this is Phase 55's own original verify step, finally achievable. Full
  detail: GOALS_TODOS.md.

PHASE 64 -- Fix core/storage.py crashing when MEDIA_ROOT doesn't exist yet (XS) (DONE)
  Found live: pushing Phase 63 triggered a real CI run of the new pytest
  step -- 64/65 passed, 1 failed:
  `google_media_backup/tests_resumable_download.py::test_task_photos_download_batch_passes_db_size_bytes_as_size_hint`
  -- `FileNotFoundError: [Errno 2] No such file or directory:
  '/__w/backdeezup/backdeezup/backend_django/media'`. This is a real bug the
  new CI step immediately caught, not a flaw in Phase 63's wiring -- passed
  locally only because this dev box happens to already have a stray
  `backend_django/media/` directory sitting around from earlier session
  activity, masking it.
  Root cause, confirmed by reading the code: `core/storage.py:24`'s
  `usage()` calls `shutil.disk_usage(settings.MEDIA_ROOT)` with no check
  that the directory exists first. `MEDIA_ROOT` defaults to `BASE_DIR /
  'media'` (`config/settings.py:158`). In the real Docker deployment this
  is masked -- `docker-compose.yml`'s `media:` named volume auto-creates
  its mount point directory the first time it's attached, even before any
  file is ever downloaded -- but a bare `manage.py`/`pytest` run with no
  Docker volume involved (exactly what CI does, and what a local dev
  environment would do before Docker is ever brought up) has no such
  guarantee. This task is called from
  `google_media_backup/tasks.py:58`'s `task_photos_download_batch`, which
  the storage guard (Phase 32) checks before every download batch --
  meaning the very first download task on a sufficiently fresh install
  (outside the lucky Docker-volume side effect) could crash before
  downloading anything.
  Fix: in `core/storage.py`'s `usage()`, ensure `MEDIA_ROOT` exists before
  calling `shutil.disk_usage()` on it (`os.makedirs(settings.MEDIA_ROOT,
  exist_ok=True)`) -- matches Django's own convention elsewhere in this
  codebase of creating storage directories defensively rather than
  assuming they exist. No test-file change needed; this is a real
  production-code gap, not a test-environment workaround.
  Verify: delete/rename `backend_django/media/` locally (or just test in a
  scratch checkout that never had one), re-run the exact failing test --
  confirm `usage()` no longer crashes and the test passes. Then confirm the
  scoped full pytest run (all 6 files, same as Phase 63's verification)
  passes cleanly. Full detail: GOALS_TODOS.md.

PHASE 65 -- Fix compose-smoke CI job: missing external "backdeezup_media" volume (XS) (DONE)
  Found live: after Phase 64 shipped, `lint`/`sast-bandit`/`test` all went
  green (Phase 55's original goal, confirmed via `gh run view --json
  status,conclusion,jobs`) -- but the overall run still showed `failure`
  because `compose-smoke` failed. Confirmed unrelated to anything from this
  session: `git log -S "external: true" -- docker-compose.yml` shows the
  `media:` volume was marked `external: true` in commit `3f83107` ("fix:
  mark backdeezup_media as external volume to suppress WARN on docker
  compose up"), which predates every phase from this session (50-64).
  `compose-smoke` has likely been broken since that commit.

  Facts confirmed by reading the actual CI log (`gh run view --log-failed`)
  and the workflow file:
    - The exact failure: `external volume "backdeezup_media" not found` on
      `docker compose up -d --build`, then `##[error]Process completed with
      exit code 1`.
    - `docker-compose.yml`'s `volumes:` section (bottom of file) declares
      `media: external: true` -- Compose will never create this volume
      itself; something has to run `docker volume create backdeezup_media`
      first.
    - `Makefile`'s `up:` target already does this correctly:
        up:
            @docker volume create backdeezup_media >/dev/null   # external volume -- Compose never creates it for you; safe to re-run
            docker compose up -d
    - `.github/workflows/ci.yml`'s `compose-smoke` job (line 204) replicates
      most of `make up`'s setup manually (writes `.env`, generates a
      self-signed cert, creates dummy Google client secrets) but its "Start
      full Docker Compose stack" step (line 271-272) is a bare
      `docker compose up -d --build` -- it never runs the volume-create
      step at all.

  Fix: add `docker volume create backdeezup_media` (matching the Makefile's
  own comment: "external volume -- Compose never creates it for you; safe
  to re-run") as its own step, or prepended to the existing "Start full
  Docker Compose stack" step, right before `docker compose up -d --build`
  in `.github/workflows/ci.yml`'s `compose-smoke` job.

  Verify: `gh run list --workflow=ci.yml --limit 1` shows `compose-smoke`
  passing (or at least progressing past the volume-creation step -- the
  job has several further smoke-test steps after it that were never
  reached and have not been verified independently; if one of those fails
  next, diagnose it separately with real log evidence rather than assuming
  this one fix closes the whole job). This dev box has no live compose
  stack to test the fix against directly -- CI itself is the verification
  environment for this one. Full detail: GOALS_TODOS.md.
  RESULT confirmed 2026-09-28 (run 36463420169): Phase 65's fix genuinely
  worked -- `compose-smoke` got past volume creation and the healthy-wait
  step this time (new progress, not seen before). It hit a DIFFERENT,
  previously-unseen failure further along. See PHASE 66.

PHASE 66 -- Diagnose compose-smoke's exit-137 on "Run Django migrations via compose" (S, diagnosis-first) (DIAGNOSTIC STEP ADDED, root cause still open)
  Size: S. Risk: n/a -- diagnosis phase; no fix decided yet.

  Trigger: after Phase 65's volume-create fix, run 36463420169 shows
  `compose-smoke` getting past "Wait for web service to be healthy"
  ("web state: running (attempt 1/30)" -- first check, immediately) but
  then dying on the very next step:
    docker compose exec -T web python manage.py migrate --run-syncdb
    ##[error]Process completed with exit code 137.
  Confirmed via `gh run view 36463420169 --log-failed`: this happens ~3
  seconds after the step starts (18:13:33.77 -> 18:13:36.76). Exit 137
  is SIGKILL -- almost always an OOM kill in a GitHub Actions container
  context, but NOT independently confirmed here (no `docker stats`/memory
  telemetry captured in this run) -- could also be a container that was
  already dead/killed moments earlier (from the OTHER 5 containers -- db,
  redis, celery, celerybeat, nginx -- all starting up around the same
  time) rather than this specific `exec` command itself being the thing
  that got killed. Genuinely new information -- never seen before this
  run, since `compose-smoke` never got this far in any prior run.

  Suspected (NOT confirmed -- do not implement a fix on this alone): a
  standard `ubuntu-latest` GitHub-hosted runner has a fixed, modest memory
  budget (~7GB, shared with runner overhead), and this job runs `docker
  compose up -d --build` for the FULL stack -- 6 containers (nginx, web,
  celery, celerybeat, db, redis) -- then almost immediately tries to run
  a SEPARATE `manage.py migrate` process inside `web`, which itself does a
  full Django app import (all installed apps: Wagtail + all google_*
  apps) at the same moment `web`'s own Gunicorn workers, `celery`'s
  worker, and `celerybeat` are ALL also independently booting and
  importing the same full Django app stack for the first time. That's a
  lot of concurrent heavy Python process startups competing for a fixed
  memory budget -- plausible, not proven.

  Diagnostic steps needed before any fix (this is the actual work of this
  phase -- do not guess a patch without this):
    a. Add a step right before "Run Django migrations via compose" that
       captures `docker stats --no-stream` and `docker compose ps` --
       confirms (or rules out) genuine memory exhaustion versus one
       container already having crashed.
    b. If (a) shows real memory pressure: consider trimming which
       containers `compose-smoke` actually needs running simultaneously
       (does this smoke test genuinely need `celery`+`celerybeat` up
       during the migration step, or could those start after migrations
       complete?), or reducing per-service worker counts specifically for
       CI (e.g. via the Phase 53 env vars -- `WEB_CPUS`/`CELERY_CPUS`
       don't cap memory the way `docker-compose.yml`'s `deploy.resources.limits`
       already do, but those limits could be the thing causing an
       in-container OOM if they're now too tight for a cold-start Django
       import -- worth checking `docker-compose.yml`'s current limits
       against what a genuinely fresh Django+Wagtail import needs).
    c. If (a) shows the `web` container was already dead: diagnose why
       separately (its own crash log via `docker compose logs web`, not
       assumed to be memory-related at all).

  Not verifiable from this dev box (no live compose stack, and CI itself
  is genuinely resource-constrained in a way this local box isn't) -- the
  diagnostic step (a) needs to run in CI and be read from a real log,
  same discipline as every other phase this session. Full detail:
  GOALS_TODOS.md.

Phase 67 -- Fix nginx proxying to a dead `web` container after `make upgrade` (S) (DONE)
  Live production bug on PDX-CL1, caught right after running `make upgrade`
  (which the user ran on my recommendation to pick up Phases 60-64). The
  script's own health check failed:

    HEALTH CHECK FAILED after the upgrade.

  Root cause, confirmed from real logs, not guessed:
    - `web-1` booted clean at 18:43:23 (gunicorn, 3 workers, zero errors)
      and `docker compose ps` showed it `Up ... (healthy)` the whole time.
    - `nginx-1` logged repeated `connect() failed (111: Connection
      refused)` to `web`'s upstream IP, for 10+ minutes straight, on every
      request the user made to the ops page in a real browser.
    - `docker inspect backdeezup-web-1`: `OOMKilled=false ExitCode=0
      Status=running` -- `web` never crashed. `free -h` on the host showed
      15Gi free. Not memory pressure.
    - `docker compose ps` showed `nginx-1` at `Up 3 hours` -- i.e. NOT
      recreated by the upgrade -- versus `web-1` at `Up 11 minutes` --
      i.e. freshly recreated with a new container (new internal IP).
    - `scripts/upgrade.sh` (Phase 49) only runs `docker compose up -d` in
      place -- it recreates `web`/`celery`/`celerybeat` (their image
      changed) but leaves `nginx` untouched (its image/config didn't
      change, so compose has no reason to touch it).
    - `nginx/nginx.conf.template`'s `location /` block does
      `proxy_pass http://web:8000;` with no `resolver` directive. Stock
      nginx resolves a bare hostname in `proxy_pass` ONCE, at
      worker-process startup, and caches that IP for the worker's entire
      lifetime -- it never re-resolves on its own. So nginx kept sending
      every request to the OLD (now-dead) `web` container's IP,
      indefinitely, until nginx itself is restarted. This is the standard,
      well-known Docker Compose + nginx trap (bare `proxy_pass` hostname +
      no `resolver` = permanently stale upstream IP across any container
      recreate that doesn't also recreate nginx).
    - Confirmed `make redeploy` does NOT have this bug: it runs `docker
      compose down` before `up -d`, which tears down and recreates nginx
      too, so nginx always gets a fresh DNS lookup on start. Only the
      in-place `upgrade` path is affected.
  Live fix already run to restore PDX-CL1 immediately: `docker compose
  restart nginx` (told to user directly, not a code change).
  Real fix (structural, not a one-off restart): make nginx re-resolve
  `web`'s IP periodically instead of caching it forever, using Docker's
  embedded DNS at 127.0.0.11 with a variable-based proxy_pass:
    resolver 127.0.0.11 valid=10s ipv6=off;
    set $upstream_web web:8000;
    proxy_pass http://$upstream_web;
  This self-heals within ~10s of any future `web` recreate, on ANY deploy
  path (upgrade, a manual `docker compose up -d --no-deps web`, etc.) --
  not just today's specific trigger -- with no change needed to
  scripts/upgrade.sh or the Makefile. upgrade.sh's health-check loop
  already waits up to 50s (10 x 5s), well past the 10s re-resolution
  window, so it will pass on its own once this ships.
  Verify: `docker compose config -q` / nginx config test
  (`docker compose exec nginx nginx -t`) after templating; then a real
  local repro -- start the stack, `docker compose up -d --force-recreate
  --no-deps web` (simulates upgrade's in-place recreate), confirm nginx
  keeps working within ~10s without a manual nginx restart. Full detail:
  GOALS_TODOS.md.

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
