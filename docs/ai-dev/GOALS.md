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

PHASES 55-65 -- CI-debugging saga (lint/sast-bandit/test fixes, tqdm crash, ops
console, rate-limit 403, pytest wiring, storage.py crash, compose-smoke volume) --
ALL DONE. Full detail moved to GOALS_DONE.md to keep this file under 1000 lines.

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

Phase 68 -- `make upgrade` must restart nginx to actually load config changes (XS) (DONE)
  Live PDX-CL1 bug, found on a SECOND `make upgrade` run -- this time with
  Phase 67's nginx.conf.template fix already pulled into the checkout.
  Health check failed AGAIN, for a different underlying reason than
  Phase 67 diagnosed, even though the symptom looked identical (502/504
  on the ops page).
  Root cause, confirmed from the real `make upgrade` output, not guessed:
    - docker-compose.yml's `nginx` service has no `build:` step (plain
      `image: nginx:stable-alpine`) and bind-mounts
      `./nginx/nginx.conf.template:/etc/nginx/nginx.conf.template:ro`.
      Its `command` is `envsubst '$NGINX_HTTPS_PORT' <
      nginx.conf.template > nginx.conf && nginx -g 'daemon off;'` -- this
      only runs ONCE, at container start.
    - `docker compose up -d` only recreates a service's container when
      ITS OWN tracked definition changes (image digest/tag, environment,
      command string, published ports, the volumes LIST) -- it never
      diffs the actual bytes of a bind-mounted file. So a change to
      `nginx.conf.template`'s contents alone is completely invisible to
      compose's up-to-date check.
    - Direct proof from the pasted `make upgrade` output's `up 6/6` step:
        Container backdeezup-nginx-1  Running   0.0s
      -- 0.0s of work, left exactly as it was -- versus
        Container backdeezup-web-1        Started  12.4s
        Container backdeezup-celery-1     Started  12.1s
        Container backdeezup-celerybeat-1 Started  11.6s
      which all show real recreate work. nginx was never touched.
    - Net effect: nginx never re-ran `envsubst`, never re-read the
      updated template, and kept running whatever config it rendered at
      its actual last start (hours/days earlier) -- meaning Phase 67's
      resolver fix was present ON DISK but never LOADED. Same visible
      symptom as Phase 67 (nginx failing to reach `web`), genuinely
      different root cause this time (nginx not restarted at all, versus
      Phase 67's nginx-restarted-but-DNS-cached scenario).
  Immediate live fix applied on PDX-CL1 (told directly to the user, not a
  code change): `docker compose restart nginx` -- this time it actually
  loads the current, correct, on-disk template (with Phase 67's resolver
  fix in it).
  Real fix: `scripts/upgrade.sh` must unconditionally force nginx to
  restart/recreate as part of every upgrade run, so ANY future
  `nginx.conf.template` edit is guaranteed to take effect on deploy --
  e.g. `docker compose up -d --force-recreate nginx` run alongside (or
  immediately after) the main `docker compose up -d` step. This is
  belt-and-suspenders with Phase 67's resolver self-heal, not a
  replacement for it: Phase 67 still matters for `web` recreates that
  happen OUTSIDE of `upgrade.sh` (e.g. a manual `docker compose up -d
  --no-deps web`), where nothing will proactively restart nginx at all.
  Verify: real repro on this dev box (no Google secrets needed, same
  style as Phase 67's verification) -- start a minimal nginx + bind-mount
  setup, change the mounted template's content on disk, run `docker
  compose up -d` and confirm (matching the real bug) nginx does NOT
  restart and does NOT pick up the change; then apply the
  `--force-recreate nginx` fix to the equivalent of `upgrade.sh` and
  confirm it now does. Full detail: GOALS_TODOS.md.

Phase 69 -- Fix dry-run preview ignoring rule conditions (sender/subject/category/etc.) (S) (DONE)
  Found while researching Phase 70 (not what was asked, but a genuine
  correctness bug in the existing rules engine's trust guarantee).
  Root cause, confirmed by reading the actual code, not guessed:
    - `apply_rule()` (services_rules.py:113-183): dry-run counts ONLY
      `GmailMessage.objects.filter(state=VERIFIED, date__lte=cutoff)`
      (line ~151) plus protected-sender/attachment excludes -- it never
      touches `rule.gmail_query` or the rule's `RuleCondition` rows at
      all for the preview.
    - The REAL (non-dry-run) path (line ~165-177) additionally runs
      `rule.gmail_query` against the LIVE Gmail API
      (`svc.users().messages().list(q=rule.gmail_query, ...)`) and
      narrows to only those matching `gmail_id`s -- this is where
      sender/subject/category/label conditions actually get applied.
    - Confirmed `rule.gmail_query` is the authoritative compiled
      representation of a rule's `RuleCondition` rows, not a separate
      unused field: api.py:597-618 (`create_rule` endpoint) calls
      `query_compiler.compile_conditions()` on the submitted conditions
      and persists the result as `gmail_query` at rule-creation time.
    - Net effect: for ANY rule with a condition beyond plain age (e.g.
      "category:promotions AND older_than:30d", or a specific sender),
      the dry-run count/preview shown to the user is a pure overcount --
      it shows every verified message older than N days, completely
      ignoring category/sender/subject/label. The REAL run, once
      executed, correctly narrows to the actual matching subset.
    - This directly undermines Phase 34's own trust mechanism:
      `dry_run_confirmation_error()` blocks Execute unless the confirmed
      count matches `rule.last_dry_run_count` -- but that stored count
      was never accurate for any condition-bearing rule to begin with.
      The safety gate has been checking against the wrong number.
  Fix: make dry-run apply the exact same live-Gmail-query cross-reference
  as the real-run path, when `rule.gmail_query` is non-empty -- i.e. run
  that block unconditionally (not gated on `if not dry_run`), and let the
  EXISTING `if dry_run: ... else: <execute>` branch continue to be the
  only thing that decides whether trash/star/label/archive calls actually
  fire. Rejected alternative: a parallel local-ORM filter compiler
  mirroring query_compiler.py's Gmail-syntax semantics against
  `GmailMessage` fields directly (faster, no live API call) -- rejected
  because (a) `labels` (the local cache of Gmail's `labelIds`) is only
  populated for messages that had no subject/from_address at discovery
  time, not backfilled for the bulk of already-archived mail, so a local
  CATEGORY filter would silently under-match; and (b) maintaining two
  independent implementations of Gmail's search semantics (one for real
  Gmail, one homemade) is a permanent drift risk -- reusing the exact
  same live-query code path for both branches has zero drift risk by
  construction. Honest tradeoff to document: dry-run now costs one live
  Gmail API call (previously "fast, no Gmail API call" per the existing
  code comment) and requires Gmail auth even for a dry run -- acceptable
  given this is the literal thing Phase 34's safety gate exists to get
  right.
  Verify: existing test files already cover rule dry-run/execute
  (tests_cleanup_safeguards.py, tests_regression.py, tests_undo_protect.py
  per earlier grep) -- extend/add a case with a condition-bearing rule
  (e.g. sender-restricted) where dry-run and a mocked real-run must now
  report the SAME count, confirming the fix; run the existing scoped
  test files locally with DATABASE_URL cleared (SQLite, matches CI) per
  this repo's standing test-suite constraint. Full detail: GOALS_TODOS.md.

Phase 70 -- Mine FOSS spam-rule corpora (SpamAssassin/Rspamd) to seed suggested
new cleanup rules from header-level heuristics Gmail's category classifier
misses (M) (DONE)
  Trigger: user wants "an agent to go through my mail from the database
  side using the API to build and improve existing rules, like a
  feedback/enhancement cycle." Researched FOSS prior art first (per
  explicit request) -- verified via GitHub API + reading actual LICENSE
  file contents, not repo badges:
    - Apache SpamAssassin (Apache-2.0, verified) -- decades of
      community-maintained heuristic rules (header regex, body phrase,
      phishing patterns) plus the public SpamAssassin Mail Corpus.
    - Rspamd (Apache-2.0, verified directly from LICENSE.md content --
      GitHub's own license badge showed NOASSERTION, a false negative)
      -- modern Lua-rule equivalent, Bayesian/ML, plus community packs
      like rspamd-rules (MIT).
    - Ruled OUT: Inbox Zero (AGPLv3 + added commercial/enterprise-use
      restriction clauses -- source-available, not OSI-compliant FOSS)
      and InboxLearn (no license file at all, "all rights reserved") --
      good conceptual prior art (layered rule-then-AI matching,
      correction-based feedback loop, human-in-the-loop candidate
      eval+rollback) but not legally reusable code.
  Scope correction made during research (see chat, not guessed): the
  original idea ("backfill Gmail's labelIds/category so rules can use
  it") turned out to already exist -- `RuleCondition.FIELD_CATEGORY`
  already compiles to Gmail's native `category:` search syntax
  (query_compiler.py:74-78) and Gmail's own classifier is already used
  by real rule execution (see Phase 69). So this phase targets the
  actual gap: signals Gmail's OWN category classifier does NOT expose
  as a rule condition at all -- header-level bulk-mail heuristics
  (`List-Unsubscribe`, `List-Id`, `Precedence: bulk`, sender/Reply-To
  domain mismatches) -- mined from SpamAssassin/Rspamd's rule catalogs
  as the starting pattern list (borrowing the PATTERN, not their code --
  their rule DSL and execution model, SMTP-time raw-message filtering,
  doesn't transfer directly to a Gmail-archive cleanup tool anyway).
  Design, grounded in what already exists in this codebase:
    - Every DOWNLOADED/VERIFIED message already has its full raw RFC822
      saved locally (`GmailMessage.raw_path`) -- this analysis is
      genuinely "from the database side" as asked: parse headers from
      the LOCAL .eml files already on disk via Python's stdlib `email`
      module, no extra Gmail API calls needed for the analysis pass
      itself (the API is only touched later, when/if a suggestion is
      accepted and turned into a real CleanupRule).
    - New read-only management command (e.g. `analyze_mail_patterns`)
      scans DOWNLOADED/VERIFIED messages, extracts the header-heuristic
      signals above per sender domain, cross-references against
      currently ENABLED rules' compiled `gmail_query` to find clusters
      NOT already covered by an existing rule, and ranks candidates by
      message count.
    - New lightweight model (e.g. `SuggestedRule`: sender_pattern,
      signal_type, message_count, sample_subjects, first_seen,
      dismissed, created_rule FK) to persist suggestions across runs --
      needed for dedupe and a review surface, not scope creep: without
      persistence, every run would re-surface the same suggestions with
      no way to track "already reviewed/dismissed".
    - NEVER auto-creates or auto-enables a CleanupRule -- a suggestion
      is only ever a starting point a human reviews and explicitly turns
      into a real rule via the EXISTING create_rule API path (api.py:597),
      identical safety posture to Phase 34's dry-run-first culture and
      the pattern borrowed from Inbox Zero's "AI proposes, rule engine
      executes" design (not its license).
  Verify: dry, read-only by construction (no Gmail API writes, no rule
  auto-creation) -- run the new command against this dev box's local
  archive (if one exists) or a small fixture set of .eml files with
  known List-Unsubscribe/Precedence headers, confirm expected sender
  clusters and counts, confirm rules already covering a cluster are
  correctly excluded from suggestions (no duplicate suggestion for
  already-ruled senders). Full detail: GOALS_TODOS.md.

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
