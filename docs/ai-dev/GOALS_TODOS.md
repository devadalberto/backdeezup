# GOALS_TODOS.md -- backdeezup operations runbook
# Full phase commands for GOALS.md dispatcher. Read-only reference.
# Live phase tracking is in TODO.md -- update checkboxes there, not here.

----------------------------------------------------------------
TOOL PALETTE -- read before executing any phase
----------------------------------------------------------------

  /security-review    Phase 4  : one-pass static scan before merging CI/CD branch
  /verify             Any      : live stack spot-check (HTTPS + admin + Celery)
  /simplify           Any      : cleanup after code changes
  graphify update .   Any      : rebuild knowledge graph after structural changes

  Agent tool (spawn subagent):
    - Use Agent(subagent_type="general-purpose") for any block marked [PARALLEL].
    - Pass all needed paths/commands in the prompt -- parallel agents share no state.
    - Collect results before proceeding past the parallel block.

  Shell: all Docker/make commands run in Debian WSL2 as user saitama.
  Repo path: /home/saitama/repos/github/devadalberto/backdeezup
  Stack entry: https://localhost:8445  (HTTP :8844 redirects)

----------------------------------------------------------------
RETRY POLICY
----------------------------------------------------------------

  Docker / make ops           : 3 attempts, 10s between
  Gmail API pipeline calls    : built-in retry in gmail-loop, no manual retry
  OAuth flow                  : 1 attempt -- interactive, no retry loop
  Any blocking error          : STOP. Diagnose, report, wait for human.

----------------------------------------------------------------
PHASE 0 -- Orient before touching anything
----------------------------------------------------------------

Step 1. Preflight:
  cd /home/saitama/repos/github/devadalberto/backdeezup && make preflight
  Must pass all checks. Fix any FAIL before proceeding.

Step 2. Stack health [PARALLEL via Agent]:
  [A] docker compose ps
      Expected: 6 containers Up (web, nginx, db, redis, celery, celery-beat)
  [B] make celery-status
      Expected: workers respond, no ERROR in output
  [C] curl -sk https://localhost:8445/admin/ -o /dev/null -w "%{http_code}"
      Expected: 302

Step 3. Read ground truth [PARALLEL via Agent]:
  [A] Read shared_context.md  (authoritative pipeline + infra state)
  [B] Read graphify-out/GRAPH_REPORT.md  (codebase map)

If stack is down: make up && make migrate, wait 30s, re-run health checks.
If containers are unhealthy: docker compose logs --tail=30 <service>

----------------------------------------------------------------
PHASE 1 -- Resume Gmail backup
----------------------------------------------------------------

Step 1. Check current progress:
  Visit https://localhost:8445/admin/gmail/dashboard/
  Or: docker compose exec web python manage.py shell -c "
    from google_gmail_backup.models import GmailMessage
    from django.db.models import Count
    print(GmailMessage.objects.values('state').annotate(n=Count('id')))"

Step 2. Discover any new message IDs not yet in DB:
  make gmail-discover
  (runs 50 pages x 500 = up to 25,000 IDs; safe to re-run -- idempotent)

Step 3. Run download loop until complete:
  make gmail-loop LIMIT=500 WORKERS=10
  Run this repeatedly (or in a terminal session) until DISCOVERED count = 0.
  Target: all ~32,463 messages reach DOWNLOADED or VERIFIED state.

Step 4. Verify downloaded messages have .eml files on disk:
  docker compose exec web python manage.py shell -c "
    from google_gmail_backup.services import gmail_verify
    gmail_verify()"
  Check dashboard -- VERIFIED count should match DOWNLOADED.

Step 5. Check disk usage:
  docker compose exec web df -h /app/data/gmail/
  Alert if >80% full -- pause loop and clear trash before continuing.

KNOWN ISSUES:
  - gmail-loop is concurrent (ThreadPoolExecutor 10 workers by default).
    If rate-limited by Gmail API, reduce: make gmail-loop LIMIT=200 WORKERS=4
  - OAuth token must include https://mail.google.com/ scope.
    If 403: delete token + make auth

----------------------------------------------------------------
PHASE 2 -- Gmail sync & reconciliation (CRITICAL FIX)
----------------------------------------------------------------

PROBLEM STATEMENT:
  When a user deletes or trashes a message in Gmail directly (via web/app),
  the local DB never learns about it. The incremental sync only tracks
  messageAdded + messageDeleted events, but Gmail "trash" is a LABEL CHANGE
  (adds TRASH label), not a deletion event. Also, if historyId goes stale
  or the sync missed events, there's no way to reconcile.

  Result: DB shows thousands of messages as VERIFIED that no longer exist
  in Gmail. User cannot trust the DB state. Rules query stale data.

THE FIX (5 sub-steps):

STEP 1 -- Add new states + fields to GmailMessage model

  File: backend_django/google_gmail_backup/models.py

  a) Add a new state to the State TextChoices enum:
       SOFT_DELETED = "SOFT_DELETED", "Soft Deleted (gone from Gmail, backup retained)"

     State machine after this change:
       DISCOVERED → DOWNLOADED → VERIFIED → (active in Gmail)
       VERIFIED → TRASHED (we trashed it via rules)
       VERIFIED → SOFT_DELETED (user deleted/trashed it directly in Gmail)
       SOFT_DELETED → DELETED (purged after retention period)
       TRASHED → DELETED (emptied from Gmail trash)

  b) Add fields to GmailMessage:
       deleted_at       = DateTimeField(null=True, blank=True, db_index=True)
       deletion_source  = CharField(max_length=30, blank=True, default="")
                          # values: "gmail_user", "cleanup_rule", "gmail_sync", "manual"
       metadata_snapshot = JSONField(default=dict, blank=True)
                          # frozen copy of subject, from, to, date, labels, size at deletion time

  c) Add constant:
       RETENTION_DAYS = 90  # soft-deleted records kept for 90 days

  d) Create migration: python manage.py makemigrations google_gmail_backup

STEP 2 -- Fix incremental sync to detect label changes

  File: backend_django/google_gmail_backup/tasks.py — task_gmail_incremental_sync()

  Current code only processes: history_types=["messageAdded", "messageDeleted"]
  Must also process: "labelAdded", "labelRemoved"

  When a TRASH label is added to a message:
    - Set state = SOFT_DELETED
    - Set deleted_at = now()
    - Set deletion_source = "gmail_user"
    - Snapshot metadata_snapshot = {subject, from_address, to_address, date, labels, size_estimate}

  When TRASH label is removed (user un-trashed):
    - If state == SOFT_DELETED: revert to VERIFIED
    - Clear deleted_at and deletion_source

  When messageDeleted fires (permanent delete):
    - Set state = DELETED
    - Set deleted_at = now() if not already set
    - Snapshot metadata if not already snapshotted

STEP 3 -- Build full reconciliation Celery task

  File: backend_django/google_gmail_backup/tasks.py (new task)

  task_gmail_reconcile():
    Purpose: compare ALL local VERIFIED/DOWNLOADED messages against live Gmail.
    Run: once per day via Celery Beat (or on-demand via make target).

    Algorithm:
      1. Get all gmail_ids from DB where state IN (VERIFIED, DOWNLOADED) — batch by 1000
      2. For each batch, call Gmail API messages.get(id=X, format="minimal")
         - If 404: message no longer exists → mark SOFT_DELETED
         - If response has TRASH label: mark SOFT_DELETED, source="gmail_user"
         - If exists and no TRASH: leave as-is (confirm still alive)
      3. Log summary: X confirmed, Y soft-deleted, Z errors

    Rate limit awareness:
      - Gmail API quota is 250 units/sec for messages.get (5 units each)
      - Batch with 0.1s sleep between batches of 50
      - On 429: exponential backoff (already handled by google-api-python-client)

    Add to Celery Beat default schedule: run daily at 03:00 UTC

    Add make target:
      make gmail-reconcile  ## Compare local DB vs live Gmail, update stale states

STEP 4 -- Retention purge task

  File: backend_django/google_gmail_backup/tasks.py (new task)

  task_purge_expired_soft_deletes():
    Purpose: permanently delete DB records (not .eml files) older than 90 days.

    Algorithm:
      1. Find all GmailMessage where state=SOFT_DELETED AND deleted_at < now() - 90 days
      2. For each: ensure metadata_snapshot is populated (safety check)
      3. Create a PurgeLog entry (new model or reuse CleanupAuditLog)
         with: gmail_id, subject, from_address, date, deleted_at, purged_at
      4. Set state = DELETED (keep the row, just change state — never hard-delete rows)
      5. Optionally: delete the .eml file from disk to reclaim space
         (configurable: PURGE_EML_FILES=true/false in .env, default false — keep backups)

    Add to Celery Beat: run weekly (Sundays 04:00 UTC)
    Add make target:
      make gmail-purge-expired  ## Purge soft-deleted records older than 90 days

STEP 5 -- Update rules engine + admin UI

  File: backend_django/google_gmail_backup/services_rules.py

  When apply_rule() trashes a message:
    - Also set deleted_at = now()
    - Also set deletion_source = "cleanup_rule"
    - Also snapshot metadata_snapshot

  File: backend_django/google_gmail_backup/admin.py

  Add to GmailMessageAdmin list_filter:
    - "state" (already there)
    - "deletion_source" (new)
  Add to list_display:
    - deleted_at
  Add admin action: "Reconcile selected messages" (re-check against Gmail API)

STEP 6 -- Tests

  File: backend_django/google_gmail_backup/tests.py or tests_reconciliation.py

  Required test cases:
    - Incremental sync with TRASH label added → state becomes SOFT_DELETED
    - Incremental sync with TRASH label removed → state reverts to VERIFIED
    - Reconciliation: message returns 404 → SOFT_DELETED
    - Reconciliation: message has TRASH label → SOFT_DELETED
    - Reconciliation: message still alive → stays VERIFIED
    - Purge: records older than 90 days get state=DELETED
    - Purge: records younger than 90 days are NOT touched
    - Rules engine: after trash, metadata_snapshot is populated
    - Protected sender messages NEVER get SOFT_DELETED by rules

STEP 7 -- Wire make targets + schedule

  Makefile additions:
    gmail-reconcile:     ## Compare local DB vs live Gmail, soft-delete stale entries
    gmail-purge-expired: ## Purge soft-deleted records older than 90 days (keeps .eml)

  Celery Beat schedule (add via seed or migration):
    task_gmail_reconcile:            daily 03:00 UTC
    task_purge_expired_soft_deletes: weekly Sunday 04:00 UTC

----------------------------------------------------------------
PHASE 3 -- Gmail cleanup
----------------------------------------------------------------

SAFETY ORDER: always protected-senders first, then dry-run rules, then execute.

Step 1. Apply protected senders (star + label + keep inbox):
  Visit https://localhost:8445/admin/gmail/ops/
  Click "Apply Protected Senders" -- safe, always run first.
  Protected: mony.bello@gmail.com, mony_littleowls@outlook.com,
             virlochov@gmail.com, julietvlhr@gmail.com

Step 2. Review and enable rules:
  Visit https://localhost:8445/admin/google_gmail_backup/cleanuprule/
  Rules are seeded but disabled. Enable only rules you've reviewed.
  Recommended first batch (low risk):
    - Trash spam folder (older than 0d) -- spam is already spam
    - Trash Promotions (older than 5d)
    - Trash Social notifications (older than 5d)

Step 3. Dry-run each enabled rule:
  For each rule: click rule in admin -> "Dry Run" action
  Review affected_gmail_ids count -- if unexpectedly high, check conditions.
  Protected senders must NOT appear in any dry-run result.

Step 4. Execute rules:
  Via admin: "Execute" action on each reviewed rule.
  Or run all at once via API:
    docker compose exec web python manage.py shell -c "
      from google_gmail_backup.services_rules import run_all_enabled_rules
      logs = run_all_enabled_rules(dry_run=False)
      for l in logs: print(l.rule.name, l.affected_count)"

Step 5. Review audit log:
  Visit https://localhost:8445/admin/google_gmail_backup/cleanupauditlog/
  Every execution creates an immutable record -- review before emptying trash.

Step 6. Empty Gmail trash (only after verifying audit log):
  Visit https://localhost:8445/admin/gmail/ops/
  Run "Empty Trash (dry-run)" first -- confirm count.
  Then run "Empty Trash" (real).
  Guard: requires >= 90% of messages backed up. Will block if below threshold.

NOTES:
  - seed_rules uses gmail_query as idempotent key. Safe to re-run: make seed-rules
  - Rules engine: backend_django/google_gmail_backup/services_rules.py:apply_rule()
  - All actions default to dry_run=True -- must explicitly pass dry_run=False

----------------------------------------------------------------
PHASE 4 -- Unblock Photos pipeline
----------------------------------------------------------------

Step 1. Delete old web client from Google Auth Platform:
  Browser: https://console.cloud.google.com/auth/clients
  Find client ID: 1ql0o9aj
  Delete it. (This client blocks photoslibrary.readonly scope from working.)

Step 2. Delete existing OAuth token (it lacks the Photos scope):
  rm /home/saitama/repos/github/devadalberto/backdeezup/secrets/google_token.json
  Or: docker compose exec web rm /app/secrets/google_token.json

Step 3. Re-authenticate with all scopes:
  make auth
  Follow the URL -> browser -> copy full redirect URL -> paste back.
  Required scopes: drive, drive.readonly, gmail.readonly, gmail.modify,
                   https://mail.google.com/, photoslibrary.readonly

Step 4. Verify Photos scope included:
  docker compose exec web python manage.py shell -c "
    import json
    t = json.load(open('/app/secrets/google_token.json'))
    print(t.get('scopes', t.get('scope', 'NO SCOPE KEY')))"
  Must include photoslibrary.readonly.

Step 5. Discover Photos media:
  make discover  (runs Drive + Photos discovery)
  Check /admin/google_media_backup/mediaitem/ for new items.

Step 6. Download Photos media:
  make download
  Monitor: /admin/ops/

NOTES:
  - DO NOT add photoslibrary.readonly back to OAuth until old client 1ql0o9aj is deleted.
  - Desktop app client only: client ID 486053539237-c454bqj13or711a74tfc8t493qlna64d
  - NEVER use web client type for OAuth in this project.

----------------------------------------------------------------
PHASE 5 -- Drive documents backup + Wagtail library
----------------------------------------------------------------

Same pipeline as email/photos: discover → download → verify → import → serve.
3.87 GB of documents. End state: all docs viewable from Wagtail at /documents/<id>/.

WHAT ALREADY EXISTS (don't reinvent):
  - list_common_files() in services_google.py — 15 MIME types
  - POST /api/sync/discover-files endpoint
  - manage.py drive_pipeline discover-files command
  - download_file() — works for binary files (PDF, Office, text)
  - VaultDocument model (source_type, source_id, keep fields)
  - /documents/<id>/ URL route (Wagtail built-in, wired in urls.py:89)
  - VaultDocumentViewSet in wagtail_hooks.py
  - deterministic_path(name, digest, kind="document")
  - copy_into_media(src, digest, ext) for SHA-256 dedup

WHAT'S MISSING (the actual work):

Step 1. Add Google native format export:
  File: backend_django/google_media_backup/services_google.py

  Add GOOGLE_EXPORT_MAP dict:
    "application/vnd.google-apps.document" → ("application/pdf", ".pdf")
    "application/vnd.google-apps.spreadsheet" → (".xlsx MIME", ".xlsx")
    "application/vnd.google-apps.presentation" → ("application/pdf", ".pdf")
    "application/vnd.google-apps.drawing" → ("application/pdf", ".pdf")

  Add _GOOGLE_NATIVE_MIMES = list(GOOGLE_EXPORT_MAP.keys())

  Add download_or_export_file(file_id, mime_type, out_path):
    if mime_type in GOOGLE_EXPORT_MAP → svc.files().export_media(fileId, mimeType=export_mime)
    else → existing download_file()

  Extend list_common_files() query to also include _GOOGLE_NATIVE_MIMES.

Step 2. Add download-docs step to drive_pipeline.py:
  File: backend_django/google_media_backup/management/commands/drive_pipeline.py

  Add "download-docs" to step choices.
  Add _download_docs(limit) method:
    qs = DriveAsset.objects.filter(state="DISCOVERED")
         .exclude(drive_id__startswith="photos:")
         .exclude(mime_type__startswith="image/")
         .exclude(mime_type__startswith="video/")
    For each: download_or_export_file(drive_id, mime_type, deterministic_path(..., kind="document"))
    State: DISCOVERED → DOWNLOADED

Step 3. Add document import to import_media.py:
  File: backend_django/media_vault/management/commands/import_media.py

  Currently skips all non-image/video (line 148: else: skipped += 1).
  Add DOC_MIMES set (same 15 from _COMMON_MIME_LIST + exported Google native extensions).
  For each VERIFIED DriveAsset with mime in DOC_MIMES:
    VaultDocument.objects.get_or_create(source_id=asset.drive_id,
      defaults={title=asset.name, file=copy_to_wagtail_docs(path), source_type="drive"})

Step 4. Celery tasks:
  File: backend_django/google_media_backup/tasks.py

  task_docs_discover(max_pages=50, page_size=200)
  task_docs_download_batch(limit=100)
  task_docs_import_vault(limit=200)

Step 5. Make targets:
  docs-discover       ## Discover Drive documents (PDF, Office, Google native)
  docs-download       ## Download documents (exports Google native → PDF/XLSX)
  docs-import         ## Import downloaded docs into Wagtail VaultDocument
  docs-run            ## Full pipeline: discover → download → verify → import
  docs-progress       ## Show document pipeline state counts

Step 6. Celery Beat schedule:
  task_docs_discover: weekly Monday 03:00 UTC
  task_docs_download_batch: nightly 02:30 UTC

VERIFICATION:
  make docs-run LIMIT=10           # test with small batch
  make docs-progress               # state counts
  # Visit /admin/wagtaildocs/ — docs browseable
  # Visit /documents/<id>/ — PDF opens inline

----------------------------------------------------------------
PHASE 6 -- Testing suite overhaul
----------------------------------------------------------------

Quality gate before FOSS release. Follows citrix-platform patterns.

Step 1. pytest config in pyproject.toml:
  [tool.pytest.ini_options] — strict-markers, strict-config
  markers: unit, integration, api, smoke

Step 2. conftest.py shared fixtures:
  mock_drive_service, mock_photos_service, mock_gmail_service
  sample_drive_asset factory, sample_gmail_message factory

Step 3. Tests:
  Unit (no DB): deterministic_path, sha256_file, MIME classification, state machine
  Integration (DB + mocked API): pipeline transitions, import dedup, reconciliation
  API: HTTP endpoints with Django test client
  Smoke: Django system check, URL resolution, Celery task registration

Step 4. Coverage: fail_under=60, show_missing

Step 5. GitHub Actions CI: lint + test + security on every push/PR

Step 6. Make targets:
  test            ## Fast: unit + smoke (<10s, no DB)
  test-full       ## Everything: lint + unit + integration + API
  test-cov        ## Coverage HTML report

----------------------------------------------------------------
PHASE 7 -- Merge CI/CD branch + tag release
----------------------------------------------------------------

Step 1. Run full test suite on feat/ci-cd-autostart:
  make test-full
  Must pass all tests. Fix any failure before merging.

Step 2. Security scan:
  /security-review
  Block on any HIGH/CRITICAL finding.

Step 3. Merge to main:
  git checkout main
  git merge feat/ci-cd-autostart
  git push git@github-dev:devadalberto/backdeezup.git main

Step 4. Confirm autostart:
  systemctl is-enabled backdeezup.service → enabled

Step 5. Verify CI/CD on GitHub:
  https://github.com/devadalberto/backdeezup/actions — all green

Step 6. Tag release:
  git tag v0.12.0
  git push git@github-dev:devadalberto/backdeezup.git v0.12.0
  Update CHANGELOG.md

----------------------------------------------------------------
PHASE 6 -- Populate vault
----------------------------------------------------------------

Step 1. Extract family images/video from downloaded .eml files:
  make gmail-extract-attachments-dry
  Review count of extractable attachments.
  Then: make gmail-extract-attachments
  Check: /admin/google_gmail_backup/gmailattachment/

Step 2. Import Drive + Gmail media into Wagtail vault:
  make import-media
  Imports to VaultImage / VaultMedia / VaultDocument based on mime type.
  EXIF is automatically stripped on import.

Step 3. Verify import:
  Visit https://localhost:8445/admin/vault/ops/
  Check counts: images, documents, videos/audio.

Step 4. Triage media:
  Visit https://localhost:8445/vault/review/
  Keyboard: K=keep, D=delete, S=skip, Z=undo

Step 5. Browse gallery:
  Visit https://localhost:8445/vault/gallery/
  Confirm thumbnails render, video streaming works.

IDENTITY GROUPS (for understanding attachment sources):
  adalberto     : jose.valdes@gmail.com + variants (all Jose's accounts)
  monica        : mony.bello@gmail.com
  little-owls   : monica_littleowls@outlook.com
  emiliano      : virlochov@gmail.com
  julieta       : julietvlhr@gmail.com

----------------------------------------------------------------
PHASE 7 -- Wrap-up
----------------------------------------------------------------

Run after every session that changes architecture, state, or conventions.
Do not skip even if earlier phases had partial failures.

Step 1. Update shared_context.md:
  - Pipeline status: Drive/Gmail/Photos counts and % complete
  - Any new infrastructure changes or conventions learned
  - Date (YYYY-MM-DD)

Step 2. Update memory files:
  /home/saitama/.claude/projects/-home-saitama-repos-github-devadalberto-backdeezup/memory/
  Update project_backdeezup.md with new pipeline status.
  Update project_ci_autostart.md if branch was merged.

Step 3. Run graphify:
  ~/.local/bin/graphify update .
  Commit: git add graphify-out/ && git commit -m "chore: graphify update"

Step 4. Commit docs:
  git add shared_context.md CHANGELOG.md TODO.md
  git commit -m "docs: update shared_context + TODO after session"

Step 5. Push:
  git push git@github-dev:devadalberto/backdeezup.git <branch>

----------------------------------------------------------------
TROUBLESHOOTING
----------------------------------------------------------------

Stack won't start:
  docker compose logs --tail=30
  Most common: .env missing key, Redis password mismatch, port conflict.

Gmail 403 / forbidden on API calls:
  Token missing scope. Delete secrets/google_token.json + make auth.
  Required: https://mail.google.com/ for batchDelete/trash operations.

Gmail loop stalls / no progress:
  Check rate limit: docker compose logs --tail=20 web | grep -i "quota\|rate\|429"
  Reduce workers: make gmail-loop LIMIT=100 WORKERS=2

Celery tasks not running:
  make celery-status  -- are workers active?
  make celery-logs    -- any ERROR or CRITICAL?
  Restart: docker compose restart celery celery-beat

Cleanup rule executed 0 messages unexpectedly:
  Check gmail_query field on the rule -- compile_conditions() may have generated
  an empty or always-false query. Review via rule-builder preview.

OAuth re-auth loop:
  Verify client type is Desktop app (installed), not web.
  Client ID: 486053539237-c454bqj13or711a74tfc8t493qlna64d
  OAuth flow starts local server on port 18444.

TLS cert not trusted in browser:
  make gen-certs && certutil -addstore Root nginx/certs/cert.pem
  (run certutil in Windows PowerShell, not WSL)

----------------------------------------------------------------
PROJECT CONTEXT
----------------------------------------------------------------

Stack: nginx (TLS :8445) | web (Gunicorn/Django :8000) | db (Postgres 16)
       redis (auth :6379) | celery (worker) | celery-beat (scheduler)

Repo:  git@github-dev:devadalberto/backdeezup.git
Path:  /home/saitama/repos/github/devadalberto/backdeezup
Main:  main | Active branch: feat/ci-cd-autostart

Version: 0.10.0 (next: 0.11.0 on CI/CD merge)
Test suite: 59 tests (make test-full)

Non-bugs (do not fix):
  - OAuth flow uses local redirect server on :18444 -- normal for headless server
  - photoslibrary.readonly de-scoped until 1ql0o9aj is deleted -- intentional
  - Celery replaces APScheduler -- APScheduler code is dead, do not re-enable

Read shared_context.md first -- it is the authoritative project ground truth.

----------------------------------------------------------------
PHASE 8 -- Human-operable FOSS release (FINAL PHASE)
----------------------------------------------------------------

PURPOSE: Claude exits. A person who has never seen this codebase must be able
to clone, configure, and run backdeezup forever using only the README.
No AI. No Claude memory. No GOALS.md. Just a human, a terminal, and make.

This phase is complete when you can answer YES to:
  "Could I delete all my Claude sessions and still operate this project?"

----------------------------------------------------------------
STEP 1 -- Verify scheduled operation works without human intervention
----------------------------------------------------------------

Celery Beat is the scheduler. Confirm the default schedule:
  docker compose exec web python manage.py shell -c "
    from django_celery_beat.models import PeriodicTask
    for t in PeriodicTask.objects.filter(enabled=True):
        print(t.name, '|', t.crontab or t.interval)"

Expected default schedule (adjust if not set):
  - gmail_incremental_sync   : every 6h
  - apply_protected_senders  : every 6h
  - run_cleanup_rules        : 06:00, 12:00, 18:00 daily

If any are missing or disabled, enable them in /admin/django_celery_beat/.

Verify a scheduled run actually happened (check after 6h):
  docker compose logs --tail=50 celery | grep -E "task-|SUCCESS|FAILURE"

Add a make target for human visibility:
  make celery-schedule   -> prints all enabled periodic tasks + next run time

----------------------------------------------------------------
STEP 2 -- make help (every target must be self-explanatory)
----------------------------------------------------------------

Add a `help` target to Makefile if not present:
  help:
      @grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-28s %s\n", $$1, $$2}'

Annotate every existing target with ## <description>:
  preflight:    ## Check Docker, .env, no CHANGE_ME, valid OAuth client type
  build:        ## Build all Docker images
  up:           ## Start all 6 containers
  redeploy:     ## Pull + build + restart + migrate (standard upgrade)
  auth:         ## Run Google OAuth flow (run once, re-run if token expires)
  gmail-loop:   ## Download + verify Gmail messages (run until complete)
  seed-rules:   ## Seed / update the 15 default cleanup rules (safe to re-run)
  test-full:    ## Lint + 59 unit tests (run before every merge)
  (etc.)

Verify: make help lists every operational target with a description a human can act on.

----------------------------------------------------------------
STEP 3 -- README: day-to-day operations section
----------------------------------------------------------------

The README must cover the three human workflows without any AI context:

  A. FIRST-TIME SETUP (once per machine):
     make preflight
     make gen-certs
     make build && make up && make migrate && make superuser
     make auth
     make seed-rules && make seed-inbox-rules
     make vault-setup
     make gmail-discover
     make gmail-loop LIMIT=500 WORKERS=10   # run until complete

  B. DAY-TO-DAY (Celery handles automatically, but human can trigger manually):
     make gmail-loop          # catch up on new messages
     # Visit /admin/gmail/ops/ to review + run cleanup rules
     # Visit /vault/review/ to triage imported media

  C. AFTER A REBOOT:
     make up                  # Docker starts automatically via autostart service
                              # but this is the manual fallback

  D. UPGRADING:
     git pull origin main
     make redeploy

Keep the language at "comfortable Linux user" level. No Django internals.
No Python. No mention of Celery internals.

----------------------------------------------------------------
STEP 4 -- README: troubleshooting section (top 5 failure modes)
----------------------------------------------------------------

Every entry must be: symptom -> one diagnosis command -> one fix command.

  1. Stack won't start after reboot
     Check: docker compose ps
     Fix:   make up

  2. Gmail stops downloading / 403 errors
     Check: docker compose logs --tail=20 web | grep -i "403\|quota\|token"
     Fix:   rm secrets/google_token.json && make auth

  3. Cleanup rules ran but deleted nothing
     Check: /admin/google_gmail_backup/cleanupauditlog/ -- affected_count = 0?
     Fix:   Re-run dry-run from /admin/gmail/ops/ and review gmail_query on the rule

  4. Celery tasks not running on schedule
     Check: make celery-status
     Fix:   docker compose restart celery celery-beat

  5. TLS cert not trusted in browser
     Check: browser shows "NET::ERR_CERT_AUTHORITY_INVALID"
     Fix:   make gen-certs then install cert to OS trust store (see README)

----------------------------------------------------------------
STEP 5 -- Sanitize repo for public FOSS release
----------------------------------------------------------------

Move AI dev files out of repo root (they confuse FOSS users):
  mkdir -p docs/ai-dev
  git mv CLAUDE.md docs/ai-dev/
  git mv AGENTS.md docs/ai-dev/
  git mv GEMINI.md docs/ai-dev/
  git mv GOALS.md docs/ai-dev/
  git mv GOALS_TODOS.md docs/ai-dev/

  NOTE: CLAUDE.md controls Claude Code behavior -- if you move it,
  Claude will no longer auto-read it. Only do this when Claude's
  work on this project is fully complete.

Verify no secrets in history:
  git log --all --full-history -- secrets/ .env
  Must show only .gitignore commits, never content commits.
  If secrets were ever committed: use git-filter-repo to purge before publishing.

Verify .gitignore is complete:
  git status -- secrets/
  git status -- .env
  git status -- nginx/certs/
  All must show "nothing to commit" (ignored).

Check for credentials in source:
  grep -rn "AIza\|ya29\.\|client_secret\|AKIA\|password" \
    --include="*.py" --include="*.yml" --include="*.env" \
    --exclude-dir=".git" --exclude-dir="graphify-out" .
  Zero hits expected.

----------------------------------------------------------------
STEP 6 -- GitHub public repo setup
----------------------------------------------------------------

  gh repo edit devadalberto/backdeezup \
    --description "Self-hosted Google Drive, Gmail, and Photos backup with intelligent cleanup rules" \
    --add-topic django \
    --add-topic gmail-backup \
    --add-topic google-drive \
    --add-topic self-hosted \
    --add-topic foss \
    --add-topic celery \
    --add-topic wagtail

  gh label create "bug" --color d73a4a --description "Something is broken"
  gh label create "question" --color d876e3 --description "Further information requested"
  gh label create "enhancement" --color a2eeef --description "New feature or improvement"

  Enable Issues: gh repo edit devadalberto/backdeezup --enable-issues

----------------------------------------------------------------
STEP 7 -- Final handoff verification
----------------------------------------------------------------

Answer YES to all of these before closing Phase 7:

  [ ] I can reboot the server and the stack comes back up on its own
  [ ] I can run make gmail-loop without looking at any Claude docs
  [ ] I can enable and run a cleanup rule from the web admin alone
  [ ] The README answers every question I had the first time I set this up
  [ ] make help lists every operational action in plain English
  [ ] No Claude session memory is needed to operate this project
  [ ] A GitHub user who finds this repo can set it up from the README
  [ ] make test-full passes clean on main
  [ ] GitHub Actions CI is green on main
