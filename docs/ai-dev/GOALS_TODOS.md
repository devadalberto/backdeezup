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
PHASE 4 -- Google Photos backup via Drive API (REPLANNED)
----------------------------------------------------------------

PROBLEM: photoslibrary.readonly scope returns 403 even with valid token and published app.
Root cause: Google's sensitive scope enforcement blocks it for unverified apps regardless
of publishing status. Not a propagation delay — confirmed after 48h+ of waiting.

SOLUTION: Drive API already has access to Google Photos images (spaces=drive).
3,500+ images confirmed visible. No console.google.com changes required. No new scope needed.

APPROACH:
  - Abandon photoslibrary scope entirely for this project
  - Remove photoslibrary.readonly from SCOPES list in services_google.py
  - Rewrite list_photos_items() to use drive API (mimeType contains 'image/')
  - Rewrite download_photos_item() to use download_file() from Drive
  - Re-discover: existing photos: prefixed DB records get cleared, replaced with drive: IDs
  - Everything else (download, verify, import to Wagtail, delete) reuses existing pipeline

Step 1. Remove photoslibrary.readonly from SCOPES in services_google.py
  File: backend_django/google_media_backup/services_google.py
  Remove the line: "https://www.googleapis.com/auth/photoslibrary.readonly",
  Keep all Drive and Gmail scopes as-is.

Step 2. Rewrite list_photos_items() to use Drive API
  File: backend_django/google_media_backup/services_google.py
  New implementation:
    def list_photos_items(page_size=200, page_token=None):
        svc = drive_service()
        if not svc:
            return ([], None)
        q = "(mimeType contains 'image/' or mimeType contains 'video/') and trashed=false"
        res = svc.files().list(
            pageSize=min(page_size, 500),
            pageToken=page_token,
            q=q,
            fields="nextPageToken, files(id,name,mimeType,size,md5Checksum)",
            spaces="drive",
            corpora="user",
        ).execute()
        # Translate to Photos-compatible format (id, filename, mimeType)
        items = [
            {"id": f["id"], "filename": f.get("name",""), "mimeType": f.get("mimeType","")}
            for f in res.get("files", [])
        ]
        return (items, res.get("nextPageToken"))

Step 3. Rewrite download_photos_item() to use Drive download
  File: backend_django/google_media_backup/services_google.py
  New implementation:
    def download_photos_item(drive_id: str, out_path: str) -> bool:
        return download_file(drive_id, out_path)
  (Drive files download identically to regular Drive media)

Step 4. Clear stale photos: records from DB
  docker compose exec web python manage.py shell -c "
    from google_media_backup.models import DriveAsset
    n = DriveAsset.objects.filter(drive_id__startswith='photos:').delete()
    print('Deleted stale photos: records:', n)"
  These used Photos Library IDs which are different from Drive IDs.

Step 5. Re-discover photos via new Drive-based pipeline
  make photos-discover   (now uses Drive API)
  Expected: 3,500+ images discovered with drive: prefixed IDs... wait, actually
  these will be regular drive IDs (no prefix) since they're Drive files.
  Check /admin/google_media_backup/driveasset/ — filter by image/* MIME types.

Step 6. Download, verify, import
  make photos-download LIMIT=500
  make photos-run        (runs full pipeline)
  make import-media      (imports to Wagtail VaultImage)

Step 7. Remove photoslibrary.readonly from .env.sample and update README
  Clean up any references to the blocked scope.

VERIFICATION:
  make photos-progress   # shows DISCOVERED/DOWNLOADED/VERIFIED counts
  Visit /vault/gallery/  # photos visible in Wagtail
  one.google.com/storage # check if Photos size dropped after delete step

NOTES:
  - Drive API sees ALL photos (originals, not compressed), including videos
  - Drive IDs and Photos Library IDs are DIFFERENT — cannot mix old photos: records with new
  - The existing 2,015 photos: records have no download_path — safe to delete and re-discover
  - Re-authentication NOT required — current token has drive.readonly already
  - Delete from Google still works via trash_or_delete(drive_id, mode="trash")

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

================================================================
GRILL FINDINGS RUNBOOKS (Phases 10-15)
================================================================

----------------------------------------------------------------
PHASE 10 -- Critical reliability fixes
----------------------------------------------------------------

STEP 1. OAuth token DB storage (grill item #1)
  Problem: secrets/google_token.json is the sole copy of the refresh token.
  If deleted or GOOGLE_ENCRYPTION_KEY lost, all Google API access dies silently.

  Fix:
    a) Add OAuthToken model (or field on GmailSyncState):
       email, encrypted_token (TextField), updated_at
    b) Update _save_creds() to write to DB AND file (DB is canonical)
    c) Update _load_creds() to read from DB first, fall back to file
    d) Add health check: GET /api/health/google → tests token validity
    e) In each Celery task: if gmail_service() returns None → log + Sentry alert

STEP 2. Celery silent failure on max retries (grill item #2)
  Problem: When a task hits max_retries, it silently stops.
  historyId never advances. Weeks of messages missed.

  Fix:
    a) Add on_failure handler to task_gmail_incremental_sync and task_gmail_reconcile:
       def on_failure(self, exc, task_id, args, kwargs, einfo):
           GmailSyncState.objects.filter(...).update(last_error=str(exc))
           if sentry_sdk: sentry_sdk.capture_exception(exc)
    b) Add last_error + last_error_at fields to GmailSyncState (migration needed)
    c) Show last_error in /admin/gmail/dashboard/ as a warning banner

STEP 3. apply_rule() 5,000 cap leaves rules incomplete (grill item #3)
  Problem: Dry-run counts from local DB (cap 5,000). Real run intersects
  with Gmail API — if 12,000 messages match but only 5,000 are processed,
  the other 7,000 remain VERIFIED and re-match next run forever.

  Fix option A (preferred): Remove the cap, process all in batches of 1,000:
    while True:
        candidates = list(qs[:1000])
        if not candidates: break
        # process + update state
        if len(candidates) < 1000: break

  Fix option B: Loop apply_rule() from run_all_enabled_rules() until
  affected_count == 0 for each rule (max 10 iterations to prevent infinite loop).

  Files: backend_django/google_gmail_backup/services_rules.py:apply_rule()
         backend_django/google_gmail_backup/services_rules.py:run_all_enabled_rules()

VERIFICATION:
  DATABASE_URL="" uv run pytest -m "unit or smoke" -q
  docker compose exec web python manage.py shell -c "
    from google_gmail_backup.services_rules import run_all_enabled_rules
    results = run_all_enabled_rules(dry_run=True)
    print(sum(a.affected_count for a in results), 'would be affected')
  "

----------------------------------------------------------------
PHASE 11 -- API hardening + index fixes
----------------------------------------------------------------

STEP 4. Drive export retry on 429/quota (grill item #4)
  Problem: download_or_export_file() returns False on 429 with no retry.
  Fix in backend_django/google_media_backup/services_google.py:
    from googleapiclient.errors import HttpError
    import time

    def download_or_export_file(file_id, mime_type, out_path):
        for attempt in range(4):
            try:
                # existing download logic
                ...
                return True
            except HttpError as e:
                if e.resp.status in (429, 500, 503):
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s, 8s
                    continue
                if e.resp.status == 403 and 'exportSizeLimit' in str(e):
                    # fall back to CSV for sheets
                    if mime_type == 'application/vnd.google-apps.spreadsheet':
                        return _export_as_csv(file_id, out_path)
                raise
        return False

STEP 5. batchDelete idempotency (grill item #5)
  Problem: Celery retry after partial execution re-trashes already-trashed messages.
  select_for_update(skip_locked=True) helps but doesn't cover cross-run races.
  Fix in services_rules.py:apply_rule():
    # Skip messages where deleted_at is within last 24h (already processed recently)
    from django.utils import timezone
    from datetime import timedelta
    qs = qs.exclude(
        deleted_at__gte=timezone.now() - timedelta(hours=24)
    )

STEP 6. from_address ILIKE performance (grill item #6)
  Problem: 4 × 32k ILIKE scans per cleanup run. No index on from_address.
  Fix:
    a) Add to GmailMessage model:
       from_email_normalized = models.EmailField(blank=True, default="", db_index=True)
    b) Override save() to populate:
       self.from_email_normalized = _normalize_email(self.from_address).lower()
    c) Add migration
    d) Backfill: GmailMessage.objects.all().update(
           from_email_normalized=Func('from_address', function='LOWER', ...)
       )  -- or management command for large table
    e) Update _is_protected() and protected sender queries to use __exact on normalized field

  Files: backend_django/google_gmail_backup/models.py
         backend_django/google_gmail_backup/services_rules.py:_protected_emails()

STEP 7. Rate limiting on rule execution (grill item #7)
  Problem: Any logged-in user can trigger 16 concurrent Gmail API rule executions.
  Fix:
    a) Add Redis lock in run_all_enabled_rules():
       from django_redis import get_redis_connection
       rc = get_redis_connection("default")
       lock_key = f"cleanup_lock:{account_email}"
       if not rc.set(lock_key, "1", nx=True, ex=600):  # 10min TTL
           raise RuntimeError("Cleanup already running for this account")
    b) Return 409 from API endpoint if lock held
    c) Show "running" state in ops console (HTMX polling)

  Files: backend_django/google_gmail_backup/services_rules.py
         backend_django/google_gmail_backup/api.py:rules_run_all()

VERIFICATION:
  make test-full
  # Manually verify: run rules twice simultaneously — second should get 409

----------------------------------------------------------------
PHASE 12 -- Performance + storage + containers
----------------------------------------------------------------

STEP 8. Reconcile without per-message API calls (grill item #8)
  Problem: task_gmail_reconcile calls messages.get() for each of 25k messages.
  At 5 quota units each, 25k × 0.1s sleep = 7 hours. Restarts from zero on failure.

  Fix (replace the per-message loop):
    a) Call messages.list(q="-in:trash", maxResults=500) to get all live inbox IDs
       (paged, ~50 pages = ~50 API calls total instead of 25,000)
    b) Collect the full set of live_ids into a Python set
    c) Query local VERIFIED+DOWNLOADED IDs as a set
    d) local_only = local_ids - live_ids → mark SOFT_DELETED
    e) Only call messages.get() for the local_only set to confirm they're truly gone
       (may be in other labels: Sent, Archive — not just inbox)

  This reduces API calls from 25,000 to ~50 + len(local_only).

  File: backend_django/google_gmail_backup/tasks.py:task_gmail_reconcile()

STEP 9. Double-storage of documents (grill item #9)
  Problem: import_media.py copies files into Wagtail storage.
  Original at deterministic_path() + Wagtail copy = 2× disk usage.

  Fix option A (safe): After VaultDocument is created and saved successfully,
  delete the original download_path file:
    os.unlink(asset.download_path)
    asset.download_path = ""
    asset.save(update_fields=["download_path"])

  Fix option B (advanced): Custom Wagtail storage backend that uses hardlinks.
  Only works on same filesystem (which it is — same Docker volume).

  Start with option A. Add to import_media.py _import_drive() document block.

STEP 11. Container resource limits (grill item #11)
  Problem: Celery runaway task can starve web container workers.
  Fix in docker-compose.yml — add deploy.resources section:

    web:
      deploy:
        resources:
          limits:
            cpus: '1.0'
            memory: 512M

    celery:
      deploy:
        resources:
          limits:
            cpus: '2.0'
            memory: 1G

    celerybeat:
      deploy:
        resources:
          limits:
            cpus: '0.1'
            memory: 128M

  Note: docker compose (v2) respects deploy.resources without swarm mode
  as of Docker Engine 20.10+. Verify with: docker stats

STEP 15. Checksum verification at download (grill item #15)
  Problem: download_file() streams to disk but never verifies content integrity.
  A partial download or corruption is invisible until Wagtail import fails.

  Fix in backend_django/google_media_backup/services_google.py:download_file():
    After successful download:
    from google_media_backup.utils import sha256_file
    actual_sha = sha256_file(out_path)
    expected_md5 = asset.md5_checksum  # pass this in as a parameter
    # Note: Drive gives MD5, not SHA-256 — use hashlib.md5 for comparison
    # Or: just verify file size matches size_bytes from API (cheaper, still catches truncation)
    if os.path.getsize(out_path) != expected_size:
        os.unlink(out_path)
        return False

  Files: services_google.py:download_file()
         drive_pipeline.py:_download() — pass size_bytes to verify

VERIFICATION:
  docker stats  # verify CPU/memory caps enforced
  make docs-run LIMIT=5  # verify docs still download correctly after fix

----------------------------------------------------------------
PHASE 13 -- Schema integrity
----------------------------------------------------------------

STEP 10. metadata_snapshot Pydantic schema (grill item #10)
  Problem: metadata_snapshot is a free-form JSONField. A field rename silently
  breaks the snapshot format with no error at write time.

  Fix:
    a) Create backend_django/google_gmail_backup/schemas.py (or add to existing):
       from pydantic import BaseModel
       from typing import Optional
       class MetadataSnapshot(BaseModel):
           subject: str = ""
           from_address: str = ""
           to_address: str = ""
           date: Optional[str] = None
           labels: list[str] = []
           size_estimate: int = 0

    b) In services_rules.py and tasks.py, replace raw dict with:
       snapshot = MetadataSnapshot(
           subject=msg.subject,
           from_address=msg.from_address,
           ...
       ).model_dump()
       msg.metadata_snapshot = snapshot

    c) Add a migration-level check constraint or at minimum a test that
       validates the schema round-trips correctly.

  Files: backend_django/google_gmail_backup/schemas.py (create or update)
         backend_django/google_gmail_backup/services_rules.py
         backend_django/google_gmail_backup/tasks.py

VERIFICATION:
  DATABASE_URL="" uv run pytest -m unit -q
  # Add a unit test: MetadataSnapshot(**snapshot_dict) must not raise

----------------------------------------------------------------
PHASE 14 -- Multi-account + restore
----------------------------------------------------------------

STEP 12. Multi-account token management (grill item #12)
  Problem: Single google_token.json. Adding a second account overwrites the first.

  Fix:
    a) Add email parameter to _save_creds(creds, email) and _load_creds(email)
    b) Token filename: secrets/google_token_{sha256(email)[:8]}.json
    c) GmailSyncState.token_path = models.CharField() to store the path
    d) gmail_service(email=None) — if email provided, load that account's token
    e) Celery tasks pass account_email from GmailSyncState rows
    f) OAuth flow: ask which account is being authenticated; save to correct file

  This is a non-breaking change — existing single-account setup still works.

  Files: backend_django/google_media_backup/services_google.py (auth functions)
         backend_django/google_gmail_backup/models.py (GmailSyncState.token_path)
         backend_django/google_gmail_backup/tasks.py (pass email to services)

STEP 13. Restore-to-Gmail (grill item #13)
  Problem: SOFT_DELETED messages with .eml on disk can't be put back in Gmail.

  Fix:
    a) Add restore_to_gmail(gmail_id) in services_gmail.py:
       svc = gmail_service()
       eml_content = open(msg.raw_path, "rb").read()
       result = svc.users().messages().insert(
           userId="me",
           body={"labelIds": ["INBOX"]},
           media_body=MediaIoBaseUpload(io.BytesIO(eml_content), mimetype="message/rfc822")
       ).execute()
       # Returns new gmail_id (different from original)

    b) Add Django admin action on GmailMessageAdmin:
       "Restore selected to Gmail inbox"

    c) Add note in UI: "Restored as new message — original thread context lost"

  Files: backend_django/google_gmail_backup/services_gmail.py
         backend_django/google_gmail_backup/admin.py

VERIFICATION:
  # Test with a single SOFT_DELETED message that has raw_path set
  # Verify it appears in Gmail inbox after restore
  # Verify DB state updated (new gmail_id stored or flagged)

----------------------------------------------------------------
PHASE 15 -- Webhooks + deduplication
----------------------------------------------------------------

STEP 14. Gmail push webhooks (grill item #14)
  Problem: 6h polling lag. New emails sit unprocessed for up to 6h.
  Gmail push notifications via Pub/Sub fire within seconds.

  Prerequisites:
    a) Create a Google Cloud Pub/Sub topic: backdeezup-gmail-push
    b) Grant gmail publish permissions to the topic
    c) Create push subscription pointing to https://<your-domain>/api/gmail/push

  Code:
    a) Add /api/gmail/push POST endpoint in api.py:
       - Verify JWT from Google
       - Decode base64 notification data
       - Call task_gmail_incremental_sync.delay() for the affected email
       - Return 200 immediately (Google retries on non-200)

    b) Add watch setup command:
       docker compose exec web python manage.py setup_gmail_watch
       Calls svc.users().watch(userId="me", body={
           "topicName": "projects/<project>/topics/backdeezup-gmail-push",
           "labelIds": ["INBOX"]
       })

    c) Add Celery Beat task task_renew_gmail_watch — weekly, renews the watch
       (watches expire every 7 days)

  Note: Requires public HTTPS endpoint. For home server: use ngrok or Cloudflare Tunnel
  during development. For production: already have nginx + TLS.

STEP 17. Cross-source SHA-256 deduplication (grill item #17)
  Problem: A photo sent as Gmail attachment AND saved to Drive creates 2 VaultImages
  with identical content but different source_ids.

  Fix in backend_django/media_vault/management/commands/import_media.py:
    Before creating VaultImage or VaultMedia:
    from google_media_backup.utils import sha256_file
    sha = sha256_file(file_path)

    existing = VaultImage.objects.filter(sha256=sha).first()
    if existing:
        # Link source_id to existing image instead of creating duplicate
        # Could store multiple source_ids in a JSONField or a separate relation
        skipped += 1
        continue

    img.sha256 = sha
    # Add sha256 field to VaultImage model (migration needed)

  Also add sha256 to VaultMedia for video dedup.

  Files: backend_django/media_vault/models.py (add sha256 field to VaultImage, VaultMedia)
         backend_django/media_vault/management/commands/import_media.py

VERIFICATION:
  # Import the same image from two sources
  # VaultImage count should be 1, not 2
  DATABASE_URL="" uv run pytest -m integration -q


================================================================
V2 UX + TRUST UPGRADES -- Phases 22-49
Source: propmt_v2_upgrades_suggested (repo root). Written 2026-09-26.
================================================================

----------------------------------------------------------------
V2 GUARDRAILS -- apply to EVERY phase 22-49
----------------------------------------------------------------
  1. ADDITIVE ONLY. New modules / urls / templates / settings. Never rename or remove an
     existing route, model field, make target, Celery task name or env var.
  2. FLAG + SAME DEFAULT. Any behavior change sits behind an env var or setting whose
     default reproduces today's behavior. USER-APPROVED EXCEPTIONS (2026-09-26), each has
     an env override that restores the old behavior: Phase 39 (bind 127.0.0.1),
     Phase 41 (non-root ON), Phase 32 (storage guard ON), Phase 34 (safeguards ON).
  3. UNTOUCHED: DriveAsset / GmailMessage state transitions and the two-proof deletion
     guard. New code READS states; it never advances them.
  4. MIGRATIONS: additive only (new table, or nullable / defaulted column). No data
     rewrite, no column drop or rename.
  5. NEW VIEWS: is_staff only, CSRF on every POST, no secrets in templates or logs.
  6. ONE PHASE = ONE COMMIT (plus its tests). Revert = `git revert <sha>`.
  7. BASELINE (do once at the start of each phase, save to scratchpad):
       make test-full                      # must be green BEFORE you start
       for u in / /admin/ /admin/ops/ /admin/reports/ /admin/gmail/dashboard/ \
                /api/gmail/progress/ /vault/ ; do
         printf '%s ' "$u"; curl -sk -o /dev/null -w '%{http_code}\n' https://localhost:8445$u
       done                                # record codes (paths: verify in config/urls.py)
  8. GATE (end of each phase): make test-full green + the same URL loop prints the same
     codes + the new URL returns 200 with real data (not just HTTP 200 -- check content).
  9. Every phase ships its own tests (unit + one Django test-client view test where a
     view is added). External APIs mocked, per Phase 6 conventions.
 10. If the gate fails: STOP, revert the phase commit, report. No "fix forward".
 11. After code changes: `graphify update .` and commit graphify-out/.

----------------------------------------------------------------
TRACK A -- MAKE IT USABLE
----------------------------------------------------------------

PHASE 22 -- TIME_ZONE from env
  Size: XS.  Risk: none.
  backend_django/config/settings.py:141 hardcodes 'America/Los_Angeles'.
  Change to: TIME_ZONE = os.environ.get("TIME_ZONE", "America/Los_Angeles")
  Add TIME_ZONE to .env.example / docs/configuration.md.
  Do NOT touch USE_TZ (already True) or Celery Beat crontab tz without checking:
  grep -n "timezone\|CELERY_TIMEZONE" backend_django/config/settings.py backend_django/celery_app.py
  If CELERY_TIMEZONE is separate, leave it alone and note it in docs.
  Verify: unset TIME_ZONE -> `manage.py shell -c "from django.conf import settings; print(settings.TIME_ZONE)"`
  prints America/Los_Angeles; TIME_ZONE=Europe/Berlin prints Europe/Berlin.

PHASE 23 -- Human-readable error mapper
  Size: S.  Risk: none (nothing calls it yet except its own tests).
  New: backend_django/core/errors.py
    humanize_error(exc_or_text) -> {"title", "hint", "code"}
    Maps: HttpError 401/403 (token / scope / API not enabled), 404, 429 (quota),
    exportSizeLimit, failedPrecondition, invalid_grant (revoked / expired token),
    ConnectionError / OperationalError (DB / Redis down), OSError ENOSPC (disk full),
    PermissionError (media dir). Unknown -> generic title + raw text kept in "code".
  Pure function, no Django imports needed. Do NOT edit tasks / services to use it here.
  Tests: one parametrized test per mapping + unknown fallback.

PHASE 24 -- System health page
  Size: S.  Risk: low (read-only).
  New: core/health.py (checks) + view in core/views.py + template core/templates/.
  URL: path("health/", ...) in config/urls.py (staff only). Also /health/json/.
  Checks, each returns ok / warn / fail + one-line detail via humanize_error:
    database (SELECT 1), migrations (unapplied count), redis (ping),
    celery worker (inspect ping, 2s timeout), beat (last heartbeat -- see below),
    queue depth (redis LLEN), failed tasks (RunLog / task errors last 24h),
    storage (shutil.disk_usage on MEDIA_ROOT), OAuth token present + expiry,
    app version (VERSION file), write test on media dir (create + delete temp file).
  Beat heartbeat: do NOT change Beat schedule; read django-celery-beat / RunLog last
  run time if available, else report "unknown".
  Never let one failing check break the page: wrap each in try/except -> "fail".
  Verify: page 200, JSON parses, stop redis container -> redis row = fail, page still 200.

PHASE 25 -- Unified dashboard (read-only)
  Size: M.  Risk: low.
  New view + template at path("dashboard/", ...). Existing pages stay untouched.
  Reuse: core.views.htmx_stats, google_gmail_backup.htmx_views.htmx_gmail_progress,
  admin_ops / reports query helpers. Import them; do not copy or edit them.
  Cards (source of each number must be a DB query -- no invented values):
    backup status, last successful backup (+ duration), items per source
    (Gmail / Drive / Photos), verified count, storage used / free, recent errors
    (humanize_error), next scheduled run (Beat, shown in TIME_ZONE), account
    connection state, cleanup state (rules enabled / paused / last run).
  HTMX refresh every 30s on the cards, reusing the existing htmx pattern.
  Landing page "/" gets ONE extra link to /dashboard/ -- nothing else changes.
  Verify: numbers equal a direct psql / manage.py shell count for 3 cards.

PHASE 26 -- Per-item status labels + Backup / Browse / Cleanup navigation
  Size: S.  Risk: low (display only).
  New: core/labels.py -- one dict mapping existing State values to user labels:
    DISCOVERED -> Discovered, DOWNLOADED -> Downloaded, VERIFIED -> Verified,
    IMPORTED -> Imported, DELETE_PENDING -> Deletion pending, DELETED -> Deleted remotely,
    plus "Safe to delete remotely" = VERIFIED with both proofs true (read the existing
    guard, do not re-implement it), "Failed" from the existing error field.
  Confirm the real State enums first: google_media_backup/models.py:45 and
  google_gmail_backup/models.py:50. Use only labels whose states exist.
  Add label chips to the dashboard tables; add a 3-link nav (Backup = /dashboard/,
  Browse = /vault/, Cleanup = /admin/gmail/dashboard/) as an include shared by the new
  pages only.
  Verify: label for each real state renders; unknown state renders raw value, no crash.

PHASE 27 -- Dashboard action buttons
  Size: M.  Risk: medium -- launches jobs. Keep the surface small.
  POST-only endpoints under /dashboard/actions/<name>/ that call .delay() on EXISTING
  Celery tasks (find names with: grep -n "@shared_task\|@app.task" -r backend_django).
  Actions: Gmail backup, Drive backup, Photos backup, verify files, import media,
  retry failed, pause / resume all.
  NOT in this phase: Execute cleanup (Phase 34 owns its confirmation flow). Preview
  cleanup may call the existing dry-run only.
  Guards: staff + CSRF; Redis lock per action (reuse the E4 lock helper from commit
  cacae26) so double-clicks do not double-enqueue; return task id.
  Pause = set a Redis / DB flag "jobs_paused" that the new buttons respect; do NOT
  revoke running tasks or edit Beat.
  Progress shown via existing progress endpoints; "N done / skipped / failed" from
  RunLog. ETA only if a rate is computable, else "--".
  Verify: click each action on a dry stack, task appears in celery logs once; second
  click within lock window says "already running".

PHASE 28 -- Browser-based OAuth
  Size: M.  Risk: medium -- auth. CLI flow (make auth) MUST keep working.
  Existing: config/urls.py:79 oauth_callback at /api/oauth/callback.
  Read services_google.py auth helpers first (graphify: services_google.py hub).
  Add /dashboard/connect/ -> builds the Google auth URL (same client secrets, same
  scopes as the CLI), stores state in session, redirects. Extend oauth_callback to also
  handle the session-state path; leave the existing CLI path behavior identical.
  Pages: scope list with one-line reason per scope, connection status + token expiry,
  Reconnect, Disconnect (deletes the stored token after confirm; never touches data).
  Errors go through humanize_error (redirect_uri_mismatch, access_denied, invalid_grant).
  Same token storage as today -- no storage change here (see Phase 10 item 1).
  Do not add multi-account UI (Phases 14 / 16-20).
  Verify: connect from browser end-to-end; then `make auth` still works; Disconnect then
  health page shows OAuth = fail with guidance.

PHASE 29 -- Setup wizard part 1
  Size: M.  Risk: medium -- security-sensitive. Must be impossible after setup.
  New app module core/setup/ . Route /setup/ .
  First-run = no superuser exists AND no SetupState row with completed=True.
  New tiny model SetupState(completed bool, step str, updated_at) -- additive migration.
  Existing installs (a superuser already exists): wizard is never reachable, /setup/
  redirects to /dashboard/. This is the regression guard -- test it explicitly.
  Steps in this phase: (1) welcome + validators, (2) create local admin account.
  Validators (reuse Phase 24 checks): DB, Redis, Celery, media write, disk space, TLS
  reachable, OAuth client file present, redirect URI matches request host.
  Each failing validator shows humanize_error text and a Recheck button.
  Account creation: Django password validators, then lock the wizard step.
  Verify: fresh DB -> wizard reachable; after admin created -> /setup/ redirects;
  existing DB -> never reachable.

PHASE 30 -- Setup wizard part 2
  Size: M.  Risk: low-medium.
  Steps 3-6 on top of Phase 29: choose services (Gmail / Drive / Photos) -> connect
  Google (Phase 28 flow) -> storage location (validated writable; display only if the
  media volume is fixed by compose) -> schedule (writes the SAME Beat entries the seed
  uses; presets daily / weekly; time in TIME_ZONE) -> run a small test backup
  (limit ~10 items via existing task with a limit arg; if the task has none, add an
  optional arg defaulting to unlimited) -> "Backup is working" screen only when the
  test items reach VERIFIED (Phase 31 definition; until then, DOWNLOADED + sha256).
  CLI workflow stays: wizard is optional.
  Verify: run wizard on a scratch DB with mocked Google -> completed=True, dashboard
  loads; rerun /setup/ -> redirect.

----------------------------------------------------------------
TRACK B -- MAKE IT TRUSTWORTHY
----------------------------------------------------------------

PHASE 31 -- Verification report + success definition + integrity check
  Size: M.  Risk: low (read-only + one new task).
  Definition (in code + docs): an item counts as "backed up" only if state >= VERIFIED
  (download + checksum + persisted file exists). Dashboard and wizard use this.
  New report /dashboard/verification/: verified count, items with missing file on disk,
  items with checksum mismatch, oldest verified, per source.
  New Celery task task_integrity_check: samples N files (setting, default 200), re-hashes
  vs stored sha256, records result in a new IntegrityRun table. It only READS files and
  WRITES its own table -- never flips item state.
  Add Beat entry weekly, gated by INTEGRITY_CHECK_ENABLED (default True is fine: it is
  read-only).
  Verify: corrupt one copied test file in a scratch volume -> report flags it.

PHASE 32 -- Storage warnings + disk precheck + auto-pause
  Size: S-M.  Risk: medium (can block jobs). DEFAULT ON (user decision 2026-09-26).
  New core/storage.py: usage(), free_gb(), estimated_days_remaining (free / avg daily
  growth from RunLog; show "--" if unknown).
  Settings: STORAGE_WARN_PCT=85, STORAGE_PAUSE_PCT=95, STORAGE_GUARD_ENABLED=True
  (set False to restore today's behavior).
  Warn: dashboard + health banner. Guard (on by default): the Phase 27 buttons and a
  wrapper check at the start of download tasks refuse to start below free-space floor.
  Wrapper must be a pre-check that returns early with a logged reason -- no change to
  task bodies.
  Verify: STORAGE_PAUSE_PCT=1 in a test -> task returns "paused: low disk"; flag off ->
  behavior identical to today. With the guard on and real disk usage below the threshold,
  the existing tasks run exactly as before (add a test for this).

PHASE 33 -- Notifications
  Size: M.  Risk: low if failures are swallowed.
  New core/notify.py: send(event, title, body) -> fan out to configured channels:
  generic webhook (JSON POST), Slack + Discord (webhook URLs), SMTP email.
  All off unless env set (NOTIFY_WEBHOOK_URL, NOTIFY_SLACK_URL, ...). A send failure
  is logged, never raised.
  Events wired one at a time, each a one-line call at an existing failure / result site
  (no logic change): backup task failure (Phase 10 on_failure handler if present),
  OAuth revoked (invalid_grant), disk low (Phase 32), no successful backup in
  N hours (new Beat check), cleanup executed, integrity check found problems (Phase 31).
  Rate-limit duplicates: same event key at most once per hour (Redis SETNX + TTL).
  Verify: point webhook at a local `python -m http.server` / nc, trigger each event.

PHASE 34 -- Cleanup safeguards
  Size: M.  Risk: medium -- touches the deletion flow, so wrap, do not rewrite.
  Read first: google_gmail_backup/services_rules.py (apply_rule), admin_views.py,
  gmail_rule_builder, CleanupRule model (action / enabled fields).
  Add, all opt-out-free but non-breaking:
    - Rule gets nullable last_dry_run_at + last_dry_run_count (additive migration).
    - New "Execute" UI path refuses until a dry run exists and is < 24h old; shows
      "This rule will move N messages ... to Gmail Trash" (N from the dry run) and
      requires typing the number or ticking a confirm box.
    - Label Trash vs permanent delete wherever the action is displayed.
    - Global pause: setting/DB flag CLEANUP_PAUSED; the run-all-enabled task and the new
      Execute path check it and no-op with a log line.
    - Per-rule "never delete messages with attachments" -> an extra condition appended
      to the compiled query via the existing RuleCondition model (no compiler edits).
  ON by default (user decision 2026-09-26): the dry-run-required + exact-count confirm
  apply to the NEW Execute UI path. Env CLEANUP_REQUIRE_DRY_RUN=0 disables the check.
  Existing make cleanup-run and Beat runs of already-enabled rules are NOT blocked by
  the dry-run requirement (that would silently stop scheduled cleanup); they only
  honor CLEANUP_PAUSED. Say so in docs.
  Verify: Execute without dry run -> refused; with dry run -> confirm screen shows the
  same count as the dry run; CLEANUP_PAUSED=1 -> run-all no-ops.

PHASE 35 -- Cleanup undo + protect sender button
  Size: S-M.  Risk: medium.
  Undo: from CleanupAuditLog rows of one run, call Gmail users.messages.untrash for ids
  still in Trash. Only works for Trash actions inside Gmail's retention window; permanent
  deletes are shown as "not restorable". Failures reported per message, never abort.
  Requires the audit log to hold message ids -- confirm in models.py:336 first; if it
  does not, this phase becomes: store ids (additive) and undo applies from then on.
  Protect: button on a message / sender row -> get_or_create ProtectedSender
  (models.py:174). Idempotent.
  Verify: run a rule on a test label, undo, messages back in INBOX; protect a sender,
  rerun rule, sender's mail untouched.

PHASE 36 -- Export to ZIP / TAR
  Size: M.  Risk: low (read-only on stored files).
  Extend google_gmail_backup/exports.py (exists) + a media export.
  New endpoint /dashboard/export/ with format (zip|tar), scope (selection | source |
  everything). Stream with a generator; never build the archive in memory. For large
  scopes, run as a Celery task writing to MEDIA_ROOT/exports/ and show a download link;
  exports/ excluded from backup discovery.
  Gmail as .eml per message. Include a manifest.json (paths + sha256).
  Verify: export 20 items, unzip, sha256 in manifest == sha256sum of files.

PHASE 37 -- Restore to local dir + conflict handling + restore test
  Size: M.  Risk: low (writes only to the chosen local dir).
  New core/restore.py: restore_items(items, dest_dir, on_conflict="skip|overwrite|rename|compare").
  compare = skip when sha256 equal, else rename. dest must be inside an allow-listed
  root (RESTORE_ROOT setting, default MEDIA_ROOT/restores) -- reject path traversal.
  Preserve mtime and folder structure from stored metadata where available.
  "Can I restore a file?" button: picks a random VERIFIED item, restores it to a temp
  dir, compares sha256, shows pass / fail, stores result in the Phase 31 IntegrityRun
  table. Optional weekly Beat entry (off by default).
  Restore to Gmail = Phase 14, not here. Restore to Drive / other account = backlog.
  Verify: each conflict mode on a pre-existing file; traversal attempt ("../") rejected.

PHASE 38 -- PostgreSQL backup / restore
  Size: S.  Risk: none to app.
  Makefile: db-backup (pg_dump -Fc via docker compose exec db, to ./backups/ with
  timestamp), db-restore FILE=... (asks confirmation, refuses without FILE), targets
  added to `make help`. ./backups/ into .gitignore.
  Optional Beat task gated by DB_BACKUP_ENABLED (default False) keeping last N dumps.
  Docs: docs/operations.md section incl. a tested restore into a scratch DB.
  Verify: db-backup -> restore into a throwaway DB -> row counts equal.

----------------------------------------------------------------
TRACK C -- MAKE IT ROBUST
----------------------------------------------------------------

PHASE 39 -- Compose healthchecks + env-driven ports
  Size: S.  Risk: medium (compose edit). Docker Desktop is the only engine here.
  docker-compose.yml facts (verified 2026-09-26): web ports "0.0.0.0:8845:18444";
  nginx "0.0.0.0:8844:80" + "0.0.0.0:8445:443"; media volume is external: true;
  db / redis / celery have healthchecks; web and celerybeat do not.
  Do:
    - web healthcheck -> curl /health/json/ (Phase 24) or a plain TCP check.
    - celerybeat healthcheck -> process check (pgrep celery) -- no schedule change.
    - Ports become ${BIND_ADDR:-127.0.0.1}:${WEB_PORT:-8845}:18444 style variables.
      DEFAULT BIND = 127.0.0.1 (user decision 2026-09-26, as the source doc recommends).
      Ports stay 8845 / 8844 / 8445. To expose on the LAN: BIND_ADDR=0.0.0.0 in .env.
      WSL mirrored networking makes 127.0.0.1 reachable from the Windows browser
      (CLAUDE.md, verified 2026-09-22); re-test that. Document the change in
      CHANGELOG + docs/deployment.md (anything reaching the stack over the LAN breaks
      until BIND_ADDR is set). Update URL_INDEX.md if it lists LAN URLs.
    - `make compose-check` = docker compose config -q.
  Baseline first: docker info --format '{{.Name}}' must print docker-desktop.
  Verify: `docker compose config` diff shows only the added variables, healthchecks and
  the 127.0.0.1 bind; all containers healthy; same URL loop from WSL AND from the
  Windows browser; BIND_ADDR=0.0.0.0 reproduces the old bindings exactly (`docker compose
  ps` port column).

PHASE 40 -- Pin uv image + .dockerignore review
  Size: XS.  Risk: low.
  Dockerfile:16 uses ghcr.io/astral-sh/uv:latest -> pin to the exact version currently
  on PATH in the image (docker run --rm <image> uv --version; do not guess a tag).
  Review .dockerignore: exclude .git, graphify-out, docs build output, .env, media,
  backups. Do not exclude anything the build COPYs -- confirm with a full build.
  Base image digest pinning = release builds only (Phase 47), not dev.
  Verify: docker compose build web succeeds; image size not larger than before.

PHASE 41 -- Non-root container
  Size: M.  Risk: HIGH (volume permissions) -> land last in Track C and test on a copy.
  DEFAULT ON (user decision 2026-09-26: best practice). Ship as ON only if the gate
  passes; if it fails, revert (Guardrail 10) and re-plan -- do not ship a half-working ON.
  Add USER appuser (fixed uid/gid, e.g. 10001) in Dockerfile; chown app dir; entrypoint
  must not need root. The external `media` and `staticfiles` volumes are root-owned
  today: provide a one-shot `make fix-perms` (docker run --rm -v media:/m alpine chown)
  and document it; do NOT auto-chown existing data silently in the entrypoint.
  Build ARG NONROOT (default 1) keeps an escape hatch: --build-arg NONROOT=0 gives the
  old root image. Add an upgrade note: run `make fix-perms` once BEFORE the first start
  of the non-root image on an existing install, and have the entrypoint fail with a clear
  message (humanize_error text) when the media dir is not writable.
  Verify: web / celery / beat healthy; a download writes a file; collectstatic works;
  entrypoint migrations run.

PHASE 42 -- Resumable downloads + checkpointing
  Size: M.  Risk: medium.
  Only for large files (> RESUME_MIN_MB, default 50). Download to <name>.part, use HTTP
  Range on retry, atomic rename when complete, THEN existing sha256 verification runs.
  Small files keep the current code path untouched. Stale .part files older than 7 days
  removed by the integrity task (Phase 31), never during a running download.
  Verify: kill the worker mid-download on a large test file, restart, file completes with
  a correct sha256 and no duplicate DB rows.

PHASE 43 -- Max concurrency + rate-limit knob
  Size: S.  Risk: low.
  Settings MAX_CONCURRENT_DOWNLOADS (default = today's effective value; read it from the
  current worker config, don't guess) and GOOGLE_API_MAX_RPS. Apply as a Redis
  semaphore / token bucket inside the new Phase 27 launchers and, only if trivial, at
  the existing per-item download call. Exponential backoff already in Phases 10-11 --
  do not re-implement; reuse.
  Expose the two settings read-only on the health page.
  Verify: set concurrency 1, enqueue 5 downloads, worker log shows serial execution.

PHASE 44 -- CI vulnerability scan + SBOM
  Size: S.  Risk: none to runtime.
  GitHub Actions job (extend existing workflow from Phase 6): trivy fs + trivy image
  (non-blocking at first: report only), and syft SBOM (SPDX JSON) uploaded as a build
  artifact. Switch to failing on CRITICAL only after one clean run.
  Verify: workflow green on a branch; SBOM artifact present.

----------------------------------------------------------------
TRACK D -- MAKE IT DISTRIBUTABLE
----------------------------------------------------------------

PHASE 45 -- README rewrite around user tasks
  Size: S.  Risk: none (docs only). Keep the old README as docs/dev-quickstart.md.
  Outline: Install -> Connect Google -> Choose what to back up -> First backup ->
  Verify -> Browse -> Restore -> Schedules -> Cleanup -> Upgrade -> Back up BackDeezUp
  itself -> Troubleshoot. Add: supported-platform matrix, minimum hardware, storage
  estimate formula (label as estimate; inputs = current item counts and sizes from the DB,
  not invented), what is / is not backed up, backup vs sync vs archive vs cleanup.
  Only describe features that exist at that commit; link to phase numbers otherwise.
  Verify: every command in the README run once on a clean clone.

PHASE 46 -- Disaster recovery + upgrade guide + config reference
  Size: S.  Risk: none.
  docs/disaster-recovery.md (uses Phase 38 + 37), docs/upgrading.md (backup DB ->
  pull -> migrate -> health page), docs/configuration.md gets a table generated by a
  small script (scripts/gen_config_ref.py) that greps os.environ.get in settings.py, so
  it cannot drift. "Common mistakes" section from troubleshoot-log entries.
  Verify: regenerate the table, `git diff` clean on second run.

PHASE 47 -- Prebuilt images + versioned releases
  Size: M.  Risk: low (CI only).
  GitHub Actions: on tag vX.Y.Z build + push ghcr.io/<owner>/backdeezup:<tag> and
  :latest, base image pinned by digest for release builds, VERSION file must equal tag
  (job fails otherwise), CHANGELOG section attached to the release.
  docker-compose.yml gains optional `image:` override via env; `build:` stays default.
  Verify: tag a pre-release (vX.Y.Z-rc1) on a branch; pull and run the image.

PHASE 48 -- Optional Caddy HTTPS profile
  Size: S.  Risk: low (profile is opt-in).
  compose profile "caddy": Caddy service in front of web, automatic HTTPS from
  DOMAIN env; default `docker compose up` unchanged (nginx path stays the default).
  Docs: when to use Caddy vs external reverse proxy.
  Verify: default up = same containers as before; `--profile caddy` serves on a test
  hostname (or internal CA locally).

PHASE 49 -- One-line installer + upgrade script
  Size: M.  Risk: medium -- writes on user machines. Prints every action; asks before
  each destructive step; supports --dry-run.
  scripts/install.sh: checks docker + compose, downloads compose file + .env template,
  generates secrets locally (never printed in full), starts stack, prints the wizard
  URL. scripts/upgrade.sh: db-backup (Phase 38) -> pull -> up -> migrate -> health check
  -> automatic instructions to roll back if health fails.
  Verify: run on a clean VM / WSL distro; run --dry-run and confirm no writes.

----------------------------------------------------------------
USER DECISIONS (2026-09-26) -- all resolved
----------------------------------------------------------------
  a. Phase 39: default bind 127.0.0.1 (as recommended); BIND_ADDR=0.0.0.0 restores LAN.
  b. Phase 41: non-root ON by default (best practice); NONROOT=0 build arg is the escape.
  c. Phases 32 / 34: guards ON by default; each has an env off-switch.
  d. ORDER: multi-account (Phases 14, 16-20) runs AFTER Track B (Phases 31-38). Tracks C
     and D are not blocked by it. Phases 28-30 assume a single account; when 14 / 16-20
     land, the wizard / OAuth pages get an "add another account" follow-up phase.
