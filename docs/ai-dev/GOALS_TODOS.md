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
V2 UX + TRUST UPGRADES -- Phases 22-49 (DONE -- runbooks removed, hygiene)
Originally sourced from a suggestions prompt (repo root, `propmt_v2_upgrades_suggested`,
written 2026-09-26) -- deleted 2026-09-27 once every phase it inspired was implemented;
see git history on this file/GOALS.md if you need its original text.
================================================================

All of Tracks A-D (Phases 22-49) are implemented and committed:
  - Tracks A + B (Phases 22-38): "Tracks A and B done: Phases 24-38 (usable + trustworthy)"
  - Track C (Phases 39-44): "Track C done: Phases 39-44 (robust)"
  - Track D (Phases 45-49): "Track D done: Phases 45-49 (distributable)"
Status: GOALS.md (each phase marked DONE). What shipped, in detail, including
bugs found and fixed along the way: CHANGELOG.md. The step-by-step runbooks that
used to live here (V2 GUARDRAILS + one block per phase) were removed once
executed -- see git history on this file if you need the original text.

----------------------------------------------------------------
USER DECISIONS (2026-09-26) -- all resolved
----------------------------------------------------------------
  a. Phase 39: default bind 127.0.0.1 (as recommended); BIND_ADDR=0.0.0.0 restores LAN.
  b. Phase 41: non-root ON by default (best practice); NONROOT=0 build arg is the escape.
  c. Phases 32 / 34: guards ON by default; each has an env off-switch.
  d. ORDER: multi-account (Phases 14, 16-20) runs AFTER Track B (Phases 31-38). Tracks C
     and D are not blocked by it. Phases 28-30 assume a single account; when 14 / 16-20
     land, the wizard / OAuth pages get an "add another account" follow-up phase.

================================================================
BUGS FOUND POST-ROADMAP
================================================================

PHASE 55 -- Fix broken CI (lint, sast-bandit, test jobs all failing)
  Size: S.  Risk: low for the lint fix (mechanical); sast-bandit and test require
  diagnosis before the fix is even chosen -- do not skip that step.

  Confirmed live via `gh run list --workflow=ci.yml` + `gh run view --log-failed`
  on run 36363155626, commit 7a9a275 (current HEAD as of this writing) -- still
  failing, not a one-off flake. Three unrelated root causes:

  STEP 1 -- lint (ready to fix, root cause fully confirmed)
    `.github/workflows/ci.yml`'s lint job runs:
      uv run ruff check backend_django/ --select E,F,W --ignore E501,E701,E702
    25 real `F401` (unused import) violations, e.g.:
      - `core.setup.views` unused in backend_django/core/tests_setup_wizard2.py:15
      - `django.utils.timezone` unused in google_gmail_backup/admin.py:94
      - `json` unused in google_gmail_backup/tests_cleanup_safeguards.py:4
      - `os` unused in google_media_backup/management/commands/drive_pipeline.py:281
      - `requests` unused in google_media_backup/services_google.py:463,465
      - several unused model imports in tests_smoke.py (Q, GmailSyncState,
        CleanupRule, ProtectedSender, CleanupAuditLog, GmailAttachment, MediaItem,
        RunLog, VaultImage, VaultMedia, VaultDocument)
    Fix: `uv run ruff check backend_django/ --select E,F,W --ignore E501,E701,E702
    --fix`, then review the diff (ruff reported all 25 as auto-fixable) --
    confirm no import removal changes runtime behavior (e.g. an import kept only
    for its side effect, though none of the listed ones look like that).

  STEP 2 -- sast-bandit (root cause CONFIRMED 2026-09-27, fix verified locally)
    `.github/workflows/ci.yml`'s sast-bandit job:
      bandit -r backend_django/ -x backend_django/**/migrations -f sarif \
        -o bandit.sarif --severity-level medium || true
      (then github/codeql-action/upload-sarif@v3 with sarif_file: bandit.sarif)
    Confirmed via `gh run view 36363155626 --log` on the "Run Bandit SAST" step
    itself (not the upload step): bandit exits with its own usage error --
      bandit: error: unrecognized arguments: backend_django/core/migrations
      backend_django/google_gmail_backup/migrations
      backend_django/google_media_backup/migrations backend_django/media_vault/migrations
    Root cause: `-x backend_django/**/migrations` is UNQUOTED in the workflow's
    `run:` block. The runner's shell (`sh -e`, dash -- no globstar) glob-expands
    `**` like a plain `*` before bandit ever sees it, so the single intended
    argument becomes 4 separate filesystem paths. The first one is consumed by
    `-x`; the other 3 land as unrecognized positional targets -> bandit prints
    usage and exits nonzero -> `|| true` swallows that exit code -> `bandit.sarif`
    is never written (or left stale/empty) -> upload-sarif's JSON parse hits EOF.
    NOT the suspected "zero-findings SARIF formatter bug" theory -- that was
    disproven: quoting the argument alone fixes it and findings are non-zero.
    Fix (verified locally with `uv tool run --with 'bandit[sarif]' bandit ...`
    against this exact repo state): quote the `-x` value so the shell passes it
    to bandit as one literal string --
      -x "backend_django/**/migrations" \
    bandit itself does its own fnmatch-style path exclusion on that string (it's
    not relying on shell globbing), so this correctly excludes all 4 migrations
    dirs. Confirmed via local run: exit 1 (real findings exist, expected --
    `|| true` still swallows it same as before), valid JSON (`json.load()`
    succeeds), 22 results at `--severity-level medium`, zero results whose file
    path contains "migrations".

  STEP 3 -- test (partially diagnosed 2026-09-27; real fix needs a PDX-CL1 run)
    `.github/workflows/ci.yml`'s test job runs:
      uv run python backend_django/manage.py test google_media_backup
      google_gmail_backup --verbosity=2
    Ends with exit code 137 (OOM-killed). Separately, Django's test discovery
    reports 6 modules as `_FailedTest` (failed to import): tests_resumable_download,
    .tests_unit (google_media_backup), .tests_cleanup_safeguards, .tests_notify_wiring,
    .tests_schemas, .tests_undo_protect (google_gmail_backup).

    New finding, confirmed from the raw `gh run view 36363155626 --log-failed`
    output (saved in full, not sampled): the `_FailedTest ... ERROR` lines are
    unittest placeholders emitted at test-discovery time, BEFORE any test runs;
    their actual ImportError tracebacks only print in unittest's end-of-run
    "ERRORS:" summary block -- which this run never reaches, because the OOM
    kill (exit 137) happens mid-suite. So (a) from below is currently
    UNANSWERABLE from any existing CI log; it requires a run that survives long
    enough to print that summary, which the OOM itself prevents.

    Also confirmed from the same log: right before the kill, the log shows a
    SECOND occurrence of `Applying wagtailusers.0015_userprofile_keyboard_shortcuts...`
    (no trailing "OK") -- the initial per-run migration block already completed
    cleanly through `wagtailusers.0014_userprofile_contrast... OK` earlier in the
    same log, followed by dozens of real tests passing. A second, later
    migration-apply appearing mid-suite (only one "Creating test database for
    alias 'default'" line exists, so this isn't a second DB alias) is consistent
    with something re-triggering database setup partway through -- worth
    checking `tests_regression.py`'s `TransactionTestCase`-based tests
    (Phases 51/52, the newest code touching this path) first, but this is a lead,
    not a confirmed cause.

    Locally confirmed (scoped, per the user's standing instruction to run only
    light/targeted test subsets here -- Google Drive/Gmail aren't reachable from
    this machine anyway, so full validation happens on PDX-CL1): running exactly
    the 6 `_FailedTest` modules together in isolation --
      timeout 90 uv run python backend_django/manage.py test
        google_media_backup.tests_resumable_download google_media_backup.tests_unit
        google_gmail_backup.tests_cleanup_safeguards google_gmail_backup.tests_notify_wiring
        google_gmail_backup.tests_schemas google_gmail_backup.tests_undo_protect -v2
    -- all pass cleanly (exit 0). So the import failure is NOT intrinsic to these
    6 files; it only manifests as part of the full two-app discovery, meaning
    either ordering/interaction with another test module, or the OOM itself
    corrupting/truncating discovery output for those 6 specifically.

    Before writing any fix, still needed (do not guess a patch without this):
      a. A CI (or PDX-CL1) run that reaches the ERRORS: summary -- only possible
         once the OOM is far enough resolved (or the run given more memory) for
         the process to survive to the end. This cannot be produced from a
         local, WSL-safe scoped run here -- run the full two-app command on
         PDX-CL1, not on this machine.
      b. Identify what's consuming memory before the OOM kill using that same
         PDX-CL1 run (e.g. `/usr/bin/time -v` or a memory profiler), focusing
         first on whichever test triggers the second migration-apply above.
    Only write the actual fix once (a) and (b) are confirmed with real
    evidence from that run -- this step's job is still diagnosis, not a
    guessed patch.

    MAJOR FINDING (b), confirmed live 2026-09-28 on PDX-CL1: with `DATABASE_URL=`
    cleared (forcing the SQLite path CI also uses), the full two-app run got much
    further than any CI log ever showed and then hung indefinitely (not crashed)
    at `google_gmail_backup.tests_reconciliation.ProtectedSenderReconcileTest
    .test_protected_sender_still_soft_deleted_on_404`.
    Root cause confirmed by reading `tasks.py` and reproducing in an isolated
    Python shell: `task_gmail_reconcile()` (`tasks.py:283-293`) paginates via
      while True:
          res = svc.users().messages().list(**params).execute()
          ...
          page_token = res.get("nextPageToken")
          if not page_token: break
    but the test only configures `svc.users().messages().get(...)`'s mock --
    `svc` itself is a bare `MagicMock()`, so `.list()` is never configured.
    Verified empirically: `MagicMock().get("nextPageToken")` returns a
    **truthy MagicMock object, the same one every call** (mock attribute
    lookups don't vary by call args unless configured) -- so `if not
    page_token: break` never fires. The loop spins forever with no `sleep`,
    and every iteration appends to that mock chain's `mock_calls` history,
    which grows unbounded -- a very plausible match for CI's exit-137 OOM
    (a fast, tight, memory-growing infinite loop, not a real production bug --
    real Gmail API responses correctly omit/`None` `nextPageToken` on the last
    page).
    Same bare-`MagicMock()`-without-`.list()` pattern found in 3 other tests in
    the same file, all of which call `task_gmail_reconcile()` and would hit the
    identical infinite loop once reached: `Reconcile404Test
    .test_404_marks_soft_deleted`, `ReconcileTrashLabelTest
    .test_trash_label_present_marks_soft_deleted`, `ReconcileMessageAliveTest
    .test_alive_message_stays_verified`. (`RulesEngineMetadataSnapshotTest`
    also uses a bare `MagicMock()` but calls `apply_rule()`, not
    `task_gmail_reconcile()` -- unaffected, confirmed by reading its test body.)
    Alphabetical test ordering explains why CI's OOM and this PDX-CL1 hang both
    show progress up through `ProtectedSenderReconcileTest` (P-r-o sorts before
    `PurgeExpiredTest`/`PurgeYoungRecordUntouchedTest` P-u-r and before
    `Reconcile404Test`/etc. R-e-c) -- it's the first of the 4 affected tests to
    run, so it hangs first and blocks the other 3 from ever executing.
    This does NOT explain the 6 `_FailedTest` import failures (those are
    discovery-time import errors, unrelated to this runtime hang) -- that part
    of (a) is still open. Fix for this part: PHASE 57 (DONE -- see CHANGELOG.md).

  Verify (after all 3 steps): `gh run list --workflow=ci.yml --limit 1` shows a
  green run on the PR/commit that carries this fix, for all three jobs
  specifically (lint, sast-bandit, test) -- not just "CI passed" as PR jobs may
  differ from the full workflow.

  ROOT CAUSE OF (a) CONFIRMED, 2026-09-28 -- the piece that was genuinely
  unobtainable before is now fully in hand:
    - With Phase 57 deployed on PDX-CL1, ran the full suite locally
      (`DATABASE_URL=` cleared, same command as always):
        DJANGO_SECRET_KEY=... GOOGLE_ENCRYPTION_KEY=... DATABASE_URL= \
          uv run python backend_django/manage.py test google_media_backup google_gmail_backup --verbosity=2
      Result: "Ran 74 tests in 5.071s / OK (skipped=2)" -- clean, fast, no
      OOM. Confirms Phase 57's infinite loop was the entire OOM story.
    - But CI's own run on this same commit (`gh run 36452103678`, triggered
      by the Phase 60 push) still fails the `test` job -- now in 45s (not the
      old multi-minute-then-OOM pattern), with real tracebacks finally
      printing, since nothing kills the process early anymore. All 6
      `_FailedTest` modules show the IDENTICAL error:
        ModuleNotFoundError: No module named 'pytest'
      ("Ran 80 tests in 7.997s / FAILED (errors=6, skipped=2)" -- CI's count
      differs slightly from the local 74/no-pytest-installed count because
      CI's environment differs, not because of a new bug -- not worth
      chasing further, the real finding is the shared root cause below.)
    - Confirmed by reading all 6 files (not guessed): every one is genuinely
      pytest-native --
        google_media_backup/tests_resumable_download.py: `import pytest`,
          bare functions (no TestCase), uses fixtures implicitly via pytest
          conventions.
        google_media_backup/tests_unit.py: `@pytest.mark.unit` classes,
          `tmp_path`/`monkeypatch` fixture args.
        google_gmail_backup/tests_cleanup_safeguards.py: `@pytest.fixture`
          (a `rule` fixture), `@pytest.mark.django_db` on every test
          function, a `settings` fixture arg (pytest-django's).
        google_gmail_backup/tests_notify_wiring.py: `@pytest.mark.django_db`
          on bare functions.
        google_gmail_backup/tests_schemas.py: `@pytest.mark.unit` class.
        google_gmail_backup/tests_undo_protect.py: `@pytest.mark.django_db`,
          `pytest.raises(RuntimeError)`.
      None of these are `unittest.TestCase` subclasses -- Django's test
      runner can import them (once `pytest` itself is importable) but would
      never actually discover any tests inside them, since unittest's
      loader only picks up TestCase subclasses.
    - `pyproject.toml` already has everything needed for these to run
      correctly, just never wired into CI:
        [project.optional-dependencies]
        test = ["pytest>=8.0", "pytest-django>=4.8", "pytest-cov>=5.0", "pytest-mock>=3.14"]
        [tool.pytest.ini_options]
        DJANGO_SETTINGS_MODULE = "config.settings"
        pythonpath = ["backend_django"]
        testpaths = ["backend_django"]
        python_files = ["tests.py", "tests_*.py", "test_*.py"]
        markers = ["unit: ...", "integration: ...", "api: ...", "smoke: ..."]
      -- matches exactly how these 6 files use `pytest.mark.unit` etc.
      Someone clearly intended a dual test-runner setup (unittest via
      `manage.py test` for most of the codebase, pytest for this subset) and
      either forgot to wire CI up for the pytest half, or it regressed.
    - `.github/workflows/ci.yml`'s `test` job's `Install dependencies` step
      is a bare `uv sync` (line 66) -- never `--extra test`, so the `test`
      optional group is never installed in CI. Confirmed via `grep -n
      "pytest"` across the whole workflow file: zero matches anywhere --
      `pytest` is never invoked in CI at all, ever.
    - Verified locally that installing + running it actually works:
        uv sync --extra test
        DJANGO_SECRET_KEY=... GOOGLE_ENCRYPTION_KEY=... DATABASE_URL= \
          uv run pytest \
            backend_django/google_media_backup/tests_resumable_download.py \
            backend_django/google_media_backup/tests_unit.py \
            backend_django/google_gmail_backup/tests_cleanup_safeguards.py \
            backend_django/google_gmail_backup/tests_notify_wiring.py \
            backend_django/google_gmail_backup/tests_schemas.py \
            backend_django/google_gmail_backup/tests_undo_protect.py \
            -v
      Result: "65 passed, 5 warnings in 7.69s" -- these tests are correct
      and valuable, they've just never been given a chance to run.
    - `git status --short` after `uv sync --extra test` confirmed no tracked
      file (e.g. `uv.lock`) was modified by installing the extra locally.
  The actual fix for this is PHASE 63 (see below) -- installing the extra
  and wiring `pytest` into CI, not a change to these test files themselves.

PHASE 61 -- Fix ops console Output panel: not collapsible, grows unbounded and drags the page (XS-S)
  Size: XS-S. Risk: none -- template/CSS only, no backend change.

  Trigger: user reported the Output panel "moving up along with the page" as
  it grows, and "the expand also seems not working (the triangle thing)" on
  `/admin/gmail/ops/`.

  Facts confirmed by reading `ops.html` (not guessed):
    - The "Output" header (line ~303) is:
        <b style="color:var(--gx)">&#9654; Output</b>
      -- a STATIC unicode triangle glyph (`&#9654;` = ▶) inside a plain `<b>`
      tag. No `onclick`, no `<details>`/`<summary>`, no JS toggle logic
      anywhere in the file for this element -- it looks clickable but does
      nothing. Confirmed via `grep -n "details\|summary"` returning zero
      matches in the whole file.
    - The container div has `position:sticky;bottom:12px;z-index:50;` (line
      ~302), and `<pre id="out">` (line ~305) has no `max-height` or
      `overflow` -- so as output text grows (e.g. the cleanup-rules dry-run
      JSON, which can be hundreds of lines across 20 rules), the box's own
      height grows unbounded, and since it's `position: sticky`, the growth
      visibly drags the surrounding page content as the sticky box's height
      changes -- matches the reported "moving up along with the page"
      exactly.
    - No other `<details>` usage exists anywhere in the codebase (grepped) --
      this will be the first, no existing pattern to break by changing it.

  Fix:
    - Replace the static `<b>▶ Output</b>` with a real `<details open>` /
      `<summary>` element -- gives a genuine, browser-native, accessible
      expand/collapse triangle for free, no JS needed:
        <details open>
          <summary style="cursor:pointer;color:var(--gx);font-weight:bold;font-family:monospace;letter-spacing:1px;">
            Output <span style="font-size:11px;color:var(--gd);font-weight:normal">— result of last action appears here</span>
          </summary>
          <pre id="out" style="margin-top:8px;max-height:320px;overflow-y:auto;">(click any button above — result appears here)</pre>
        </details>
    - Add `max-height:320px;overflow-y:auto;` to `<pre id="out">` so long
      output scrolls WITHIN its own fixed-size box instead of growing the
      sticky container and dragging the page.
    - Keep `position:sticky;bottom:12px;` on the outer `.card` div -- that
      part of the intent (stay visible without scrolling to the bottom after
      every action) is fine; it's the unbounded growth that was the actual
      bug, not the sticky positioning itself.

  Verify: open `/admin/gmail/ops/` in a browser, click the `<summary>` to
  confirm it now genuinely collapses/expands (native browser behavior, easy
  to eyeball); trigger an action with long output (e.g. a rules dry-run) and
  confirm the Output box stays a fixed size with its own scrollbar instead of
  growing/dragging the page. This is a template-only change with no way to
  verify headlessly from this dev box (no browser here) -- verify visually on
  PDX-CL1 or via a screenshot after deploying.

  STATUS: DONE (2026-09-28). Applied the exact fix above -- replaced the
  static `<b>▶ Output</b>` with `<details open><summary>...</summary><pre
  id="out" style="...max-height:320px;overflow-y:auto;">...</pre></details>`,
  no other markup changed. Verified the template still parses correctly via
  Django's template engine (`engines['django'].get_template(...)`, no
  render needed since that only checks syntax, not runtime context) --
  clean, no errors. Visual confirmation (does it actually collapse/expand
  and stay fixed-size in a real browser) still needs to happen on PDX-CL1 --
  no browser available on this dev box.

PHASE 62 -- Fix django_ratelimit's Ratelimited returning raw Django 403 instead of clean JSON (XS-S)
  Size: XS-S. Risk: low -- adds one exception handler to the `gmail_api`
  NinjaAPI instance; doesn't change any rate-limit values or endpoint logic.

  Trigger: user clicked "Execute" on a cleanup rule and got a raw, unstyled
  page reading "403 Forbidden" with no explanation -- reported as an error.

  Facts confirmed (not guessed):
    - `api.py` has 4 `@ratelimit(key="user", ..., block=True)`-decorated
      endpoints, all on `gmail_api`: `/sync/discover` (5/h, line 84),
      `/rules/{rule_id}/execute` (10/h, line 449), `/rules/run-all` (3/h,
      line 468), `/audit-log/{audit_id}/undo` (10/h, line 494). Confirmed via
      `grep -rln "@ratelimit"` that no other file/API instance in the
      codebase uses this decorator -- the fix only needs to touch `gmail_api`.
    - `django_ratelimit`'s `Ratelimited` exception (raised when `block=True`
      and the rate is exceeded) is a subclass of `django.core.exceptions.PermissionDenied`
      -- confirmed via `Ratelimited.__mro__`.
    - Ninja has no built-in handler for `Ratelimited`, so it propagates up to
      Django's own default exception-to-response conversion, which calls
      `django.views.defaults.permission_denied` -- confirmed byte-for-byte by
      rendering that exact view locally and comparing its output to the raw
      HTML the user saw: both are
        '\n<!doctype html>\n<html lang="en">\n<head>\n  <title>403 Forbidden</title>\n</head>\n<body>\n  <h1>403 Forbidden</h1><p></p>\n</body>\n</html>\n'
      -- an exact match, confirming this is Django's generic 403 page, not
      nginx or anything else.
    - Given the user has been extensively testing/re-clicking rule actions
      this session (Phase 60 debugging, etc.), hitting the `10/h` execute
      limit (or the `3/h` run-all limit -- also plausible for the earlier
      "dry-run seemed stuck" report) is very plausible and not itself a bug --
      the rate limit is a reasonable safety feature. The bug is purely the
      broken/unhelpful error presentation.

  Fix (verified working end-to-end with `ninja.testing.TestClient` against a
  throwaway `NinjaAPI` instance before writing the real code -- confirmed
  `429` + clean JSON body, not a guess):
    In `api.py`, near `gmail_api`'s definition, add:
        from django_ratelimit.exceptions import Ratelimited

        @gmail_api.exception_handler(Ratelimited)
        def ratelimited_handler(request, exc):
            return gmail_api.create_response(
                request,
                {"error": "Rate limit exceeded. Please wait before trying again."},
                status=429,
            )
    `429 Too Many Requests` is the semantically correct status (not `403`,
    which implies a permissions problem rather than a temporary rate limit).
    This is registered ONCE on `gmail_api` and covers all 4 rate-limited
    endpoints uniformly -- no per-endpoint changes needed.

  Verify: the isolated `TestClient` reproduction above already proves the
  mechanism works (`STATUS: 429`, clean JSON `{"error": "..."}`). After
  applying to the real `api.py`, confirm `gmail_api`'s full URL list still
  loads (`manage.py check` / import the module cleanly) -- can't safely
  trigger a REAL rate-limit hit against a live deployment from this dev box
  without an actual running stack; the isolated reproduction is the
  practical ceiling of verification here. Full confirmation happens
  naturally the next time someone gets rate-limited on PDX-CL1 and sees a
  clean JSON message instead of a bare "403 Forbidden" page.

  STATUS: DONE (2026-09-28). Applied the exact fix above -- added `from
  django_ratelimit.exceptions import Ratelimited` and the
  `@gmail_api.exception_handler(Ratelimited)` handler right after
  `gmail_api`'s definition. Verified against the REAL module (not just the
  throwaway isolated instance):
    - `from google_gmail_backup.api import gmail_api` -- imports cleanly,
      `gmail_api._exception_handlers` includes
      `django_ratelimit.exceptions.Ratelimited` alongside Ninja's built-in
      handlers (`Exception`, `Http404`, `HttpError`, `ValidationError`).
    - `gmail_api.urls` builds successfully (a tuple) -- confirms no
      route/decorator registration conflicts across all endpoints,
      including the 4 rate-limited ones.
    - Called the real `ratelimited_handler(request, Ratelimited())`
      directly with a `RequestFactory`-built request: returns `429` with
      body `{"error": "Rate limit exceeded. Please wait before trying
      again."}` -- exact match to what was verified in isolation, now
      confirmed against the actual production code path.
  Could not trigger a real rate-limit hit through the full decorator chain
  from this dev box (no live compose stack, no reason to spin one up just
  for this) -- calling the handler directly with the exception it's
  designed to catch is the practical ceiling of verification here. Full
  live confirmation happens the next time someone gets rate-limited on
  PDX-CL1.

PHASE 63 -- Wire pytest into CI so it actually runs the 6 pytest-native test files (S)
  Size: S. Risk: low -- CI workflow only, no application code touched.
  Completes Phase 55's `test` job, once and for all.

  Trigger: Phase 55's root-cause investigation (see that section above) fully
  diagnosed the last remaining CI failure: all 6 previously-`_FailedTest`
  modules fail with the identical `ModuleNotFoundError: No module named
  'pytest'`, because they're genuinely pytest-native tests that CI never
  installs pytest for and never runs via `pytest`.

  Facts confirmed (full detail in Phase 55's entry above -- summarized here
  for the fix itself):
    - `pyproject.toml:46-51` already declares a `test` optional-dependency
      group (`pytest`, `pytest-django`, `pytest-cov`, `pytest-mock`) and
      `pyproject.toml:74-90` already has a full `[tool.pytest.ini_options]`
      config matching exactly how these 6 files use `pytest.mark.unit`/
      `django_db`/fixtures.
    - `.github/workflows/ci.yml`'s `test` job's `Install dependencies` step
      (line 66) is a bare `uv sync` -- never installs the `test` extra.
      `grep -n "pytest" .github/workflows/ci.yml` returns zero matches --
      `pytest` is never invoked anywhere in CI.
    - Verified locally: `uv sync --extra test` then running exactly these 6
      files via `uv run pytest <files> -v` -> "65 passed, 5 warnings in
      7.69s". These tests are correct and valuable; they've just never had
      the chance to run.

  Fix: in `.github/workflows/ci.yml`'s `test` job (lines 53-72):
    1. Change line 66 from `run: uv sync` to `run: uv sync --extra test`.
    2. Add one new step, after the existing "Run tests (SQLite)" step,
       scoped to exactly the 6 files (NOT a bare `uv run pytest` across
       `backend_django/` -- that would also re-collect and re-run every
       unittest.TestCase-based file the existing `manage.py test` step
       already covers, since pytest can discover and execute unittest-style
       TestCase subclasses too -- wasteful double-execution, not a
       correctness issue, but no reason to pay that CI-time cost):
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
    3. No new `env:` needed for this step -- the workflow-level `env:` block
       (lines 9-13: `DJANGO_SECRET_KEY`, `DATABASE_URL: ""`, etc.) already
       applies to every step in every job, confirmed by the existing
       `manage.py test` step relying on the same mechanism without a
       step-level override.

  Verify: `gh run list --workflow=ci.yml --limit 1` on the commit carrying
  this fix shows ALL THREE jobs green -- lint, sast-bandit, AND test. This
  is Phase 55's own original verify step from when it was first written up,
  finally achievable once this lands. If the new pytest step somehow fails
  in CI despite passing locally, do not guess -- pull the actual CI log
  (same discipline as every other phase this session) before changing
  anything.

  STATUS: DONE (2026-09-28). Applied the exact fix above to
  `.github/workflows/ci.yml`'s `test` job: `uv sync` -> `uv sync --extra
  test`, plus one new "Run tests (pytest-native)" step scoped to exactly
  the 6 files. Verified locally twice: `python3 -c "import yaml; ...
  yaml.safe_load(...)"` confirms the workflow file is still valid YAML with
  the new step present in the job's step list; and re-ran the exact pytest
  command with CI-matching env vars (`DJANGO_SECRET_KEY`,
  `GOOGLE_ENCRYPTION_KEY`, `DATABASE_URL=` empty, same as CI's own workflow
  env block) -- "65 passed, 5 warnings in 7.50s", matching the earlier
  isolated verification exactly. Actual CI-green confirmation (this phase's
  own Verify step) will happen once this commit is pushed -- can't run
  GitHub Actions from this dev box, only reproduce its exact command
  locally.

  CI RESULT after pushing (2026-09-28): confirmed 64/65 passed -- exactly
  one new, real, previously-invisible failure. See PHASE 64 below.

PHASE 64 -- Fix core/storage.py crashing when MEDIA_ROOT doesn't exist yet (XS)
  Size: XS. Risk: none -- one defensive `os.makedirs` call, no behavior
  change once the directory already exists (the common case).

  Trigger: Phase 63's push triggered a real CI run. Result: 64/65 passed,
  1 failed --
    google_media_backup/tests_resumable_download.py::test_task_photos_download_batch_passes_db_size_bytes_as_size_hint
    FileNotFoundError: [Errno 2] No such file or directory:
    '/__w/backdeezup/backdeezup/backend_django/media'
  Not a flaw in Phase 63's CI wiring -- the wiring is correct and did
  exactly its job: ran a test for the first time ever and it immediately
  caught something real. Passed locally only because this dev box already
  has a stray `backend_django/media/` directory from earlier session
  activity (confirmed via `ls -la backend_django/media`), which happened to
  mask the bug here.

  Facts confirmed by reading the code (not guessed):
    - `core/storage.py:22-26`:
        def usage():
            du = shutil.disk_usage(settings.MEDIA_ROOT)
            ...
      No existence check on `settings.MEDIA_ROOT` before calling
      `shutil.disk_usage()`.
    - `config/settings.py:158`: `MEDIA_ROOT = config('MEDIA_ROOT',
      default=str(BASE_DIR / 'media'))` -- defaults to
      `backend_django/media`, matching the exact path in CI's error.
    - `google_media_backup/tasks.py:58`'s `task_photos_download_batch` is
      the caller the failing test exercises; this is the storage guard
      (Phase 32) that runs before every download batch -- so the very
      first download task on a sufficiently fresh install could crash
      before downloading anything.
    - Why this has never been seen in real deployments: `docker-compose.yml`'s
      `media:` named volume (line 40's mount, confirmed via `docker-compose.yml`
      grep) auto-creates its mount point directory the moment it's first
      attached to a container -- before any file is ever written into it.
      Docker's volume-mount side effect papers over the missing
      `os.makedirs` call. CI's bare `python manage.py test`/`pytest` run
      has no Docker volume involved at all, so nothing creates the
      directory -- exposing the real gap.

  Fix: in `core/storage.py`'s `usage()`, ensure the directory exists before
  measuring it:
      import os
      ...
      def usage():
          os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
          du = shutil.disk_usage(settings.MEDIA_ROOT)
          ...
  This is a real production-code fix, not a test-environment workaround --
  the same gap would bite a genuinely fresh non-Docker install (e.g. local
  dev via `manage.py runserver` before anything else has touched
  `MEDIA_ROOT`).

  Verify: temporarily rename/move `backend_django/media/` out of the way
  locally (confirm it doesn't exist), re-run exactly the failing test:
      DJANGO_SECRET_KEY=... GOOGLE_ENCRYPTION_KEY=... DATABASE_URL= \
        uv run pytest backend_django/google_media_backup/tests_resumable_download.py -v
  -- confirm it now passes with `MEDIA_ROOT` absent. Then re-run the full
  scoped 6-file pytest command from Phase 63 to confirm nothing else
  regressed. Restore/leave the directory as it was after (don't leave the
  dev box in a different state than before verifying).

  STATUS: DONE (2026-09-28). Applied the exact fix above: `import os` +
  `os.makedirs(settings.MEDIA_ROOT, exist_ok=True)` right before
  `shutil.disk_usage()` in `usage()`. Verified exactly as planned:
    - Moved the real `backend_django/media/` (including its `video/`
      subdirectory) to a scratch backup, confirmed via `ls` that
      `backend_django/media` genuinely didn't exist.
    - Re-ran `tests_resumable_download.py` alone: 14/14 passed, including
      the previously-failing `test_task_photos_download_batch_passes_db_size_bytes_as_size_hint`.
    - Re-ran the full 6-file scoped set from Phase 63: "65 passed, 5
      warnings in 7.50s" -- clean, matching Phase 63's own verification
      exactly, now for real (not masked by a stray local directory).
    - Restored the original `backend_django/media/` content from the
      scratch backup afterward -- confirmed via `git status --short` that
      `media/` isn't git-tracked anyway (gitignored), so this was purely
      about not leaving the dev box's working state different from before.
  Not yet confirmed against actual CI (needs the commit pushed first) --
  the local reproduction (moving the directory away, matching CI's exact
  missing-directory condition) is the practical ceiling of verification
  here, and it's a faithful reproduction, not a guess.

  CI RESULT after pushing (2026-09-28): confirmed via `gh run view --json
  status,conclusion,jobs` on run 36459787781 -- `lint: success`,
  `sast-bandit: success`, `test: success`. Phase 55's original 3-job goal
  is achieved. Overall run conclusion is still `failure` because a fourth,
  unrelated job (`compose-smoke`, never part of Phase 55's scope) failed.
  See PHASE 65 below.

PHASE 65 -- Fix compose-smoke CI job: missing external "backdeezup_media" volume (XS)
  Size: XS. Risk: none -- one added CI step, no application/compose logic
  change.

  Trigger: after Phase 64 shipped and all three of Phase 55's target jobs
  went green, the overall CI run (36459787781) still showed `failure`
  because `compose-smoke` failed.

  Facts confirmed (not guessed):
    - Real failure log (`gh run view 36459787781 --log-failed`), tail of
      the "Start full Docker Compose stack" step:
        Network backdeezup_default  Created
        external volume "backdeezup_media" not found
        ##[error]Process completed with exit code 1.
    - `docker-compose.yml`'s `volumes:` section declares
      `media: external: true` -- Compose never creates an external volume
      itself; it must already exist before `docker compose up` runs.
    - `git log -S "external: true" --oneline -- docker-compose.yml` ->
      commit `3f83107` ("fix: mark backdeezup_media as external volume to
      suppress WARN on docker compose up") -- predates every phase from
      this session (50 through 64). This is a pre-existing gap, not a
      regression introduced by Phase 53 or 58 (the two phases that did
      touch `docker-compose.yml` this session), confirmed by checking that
      neither of those phases' diffs touched the `volumes:` section.
    - `Makefile`'s `up:` target already handles this correctly
      (Makefile:112-114):
        up:
            @docker volume create backdeezup_media >/dev/null   # external volume (docker-compose.yml) -- Compose never creates it for you; safe to re-run
            docker compose up -d
    - `.github/workflows/ci.yml`'s `compose-smoke` job (starts line 204)
      replicates most of `make up`'s setup by hand -- writes `.env`
      (line 237-269), generates a self-signed cert (210-218), creates
      dummy Google client secrets (220-235) -- but its "Start full Docker
      Compose stack" step (271-272) is a bare `docker compose up -d
      --build`, never the volume-create step.

  Fix: add `docker volume create backdeezup_media` before `docker compose
  up -d --build` in the "Start full Docker Compose stack" step (or as its
  own preceding step) in `.github/workflows/ci.yml`'s `compose-smoke` job.
  `docker volume create` is idempotent/safe to re-run (matches the
  Makefile's own comment), so no conditional/existence-check needed.

  Verify: `gh run list --workflow=ci.yml --limit 1` / `gh run view --json
  status,conclusion,jobs` on the commit carrying this fix -- confirm
  `compose-smoke` gets past volume creation. The job has several further
  steps after it (wait-for-healthy, run migrations, 3 HTTP smoke tests)
  that have never been exercised successfully before (this whole job has
  likely been broken since commit `3f83107`) -- if one of THOSE fails
  next, that is new information requiring its own real-log diagnosis, not
  something to assume is also fixed by this one change. This dev box has
  no live compose stack to test against directly; CI itself is the
  verification environment here.

  SCOPE EXPANDED during implementation: `grep -n "Start full Docker Compose
  stack"` found a SECOND occurrence (line 420-ish) in the `playwright` job
  -- it independently brings up its own full compose stack (separate
  runner, `needs: compose-smoke`, currently shows as `skipped` since it
  never gets to run while `compose-smoke` fails first) with the exact same
  bare `docker compose up -d --build`, same bug. Applied the identical fix
  to both occurrences (`replace_all` on the identical text) rather than
  treating it as a separate phase, since it's the same root cause and same
  one-line fix, just a second copy of the same pattern.

  STATUS: DONE (2026-09-28). Applied `docker volume create backdeezup_media`
  immediately before `docker compose up -d --build` in both the
  `compose-smoke` and `playwright` jobs' "Start full Docker Compose stack"
  steps. Verified: `python3 -c "import yaml; yaml.safe_load(...)"` confirms
  the workflow file is still valid YAML, and both jobs' step lists are
  otherwise unchanged (same step names/order, just the one new command
  line inside the existing step). Real CI-green confirmation (this phase's
  own Verify step) needs the commit pushed -- can't run GitHub Actions or
  a full compose stack from this dev box.

  CI RESULT after pushing (2026-09-28, run 36463420169): confirmed the fix
  genuinely worked -- `compose-smoke` got past "Start full Docker Compose
  stack" (no more "external volume not found") and past "Wait for web
  service to be healthy" ("web state: running (attempt 1/30)") -- real,
  new progress, never seen in any prior run. It then hit a DIFFERENT
  failure on the very next step. This is exactly the "if one of THOSE
  fails next, diagnose it separately" scenario this runbook called out in
  advance -- see PHASE 66.

PHASE 66 -- Diagnose compose-smoke's exit-137 on "Run Django migrations via compose" (S, diagnosis-first)
  Size: S. Risk: n/a -- this phase is diagnosis only, no fix decided yet;
  do not write a fix until the diagnostic evidence in step (a) below
  exists.

  Trigger: run 36463420169 (Phase 65's own verification push) -- full log
  via `gh run view 36463420169 --log-failed`:
    compose-smoke  Run Django migrations via compose
      2026-09-28T18:13:33.769Z ##[group]Run docker compose exec -T web python manage.py migrate --run-syncdb
      2026-09-28T18:13:36.757Z ##[error]Process completed with exit code 137.
  ~3 seconds from step start to SIGKILL. Immediately preceding step's full
  output (via `gh run view --log`, not just `--log-failed` since this one
  succeeded):
    compose-smoke  Wait for web service to be healthy
      web state: running (attempt 1/30)
      web is running
  -- i.e. the FIRST poll already reported "running", so the wait loop
  exited almost instantly (one `sleep 5` and it moved on) rather than
  actually waiting through multiple retries.

  What's confirmed vs. not, precisely:
    - CONFIRMED: exit 137 (SIGKILL) on this exact command, this exact
      step, ~3s after start, in this exact CI run.
    - CONFIRMED: this is new -- no prior `compose-smoke` run ever reached
      this step, since every earlier run failed earlier (missing volume,
      before Phase 65).
    - NOT CONFIRMED: whether this is a genuine OOM kill of the `migrate`
      process itself, or `docker compose exec` failing against a `web`
      container that had ALREADY been OOM-killed moments earlier by
      something else (the "running" state Docker Compose reports only
      means the container's top-level process started -- it says nothing
      about whether Gunicorn finished binding or whether the container
      later died from memory pressure caused by the other 5 containers
      -- db, redis, celery, celerybeat, nginx -- all starting around the
      same time). No `docker stats`/`docker compose ps` snapshot exists
      from this run to distinguish these two explanations.
    - SUSPECTED, not proven: a standard `ubuntu-latest` GitHub-hosted
      runner's fixed (~7GB) memory budget, shared across 6 simultaneously-
      starting containers -- several of which (`web`, `celery`,
      `celerybeat`) each do a full, independent Django+Wagtail app import
      on cold start -- plus this `exec`'d `migrate` process ALSO doing a
      full Django app import at the same moment, could plausibly exhaust
      available memory. This is a real, but unverified, hypothesis.

  Diagnostic steps required before any fix (the actual deliverable of this
  phase):
    a. Add a CI step, right before "Run Django migrations via compose",
       that captures and prints `docker stats --no-stream` and `docker
       compose ps` (and ideally `free -h` for the runner's own overall
       memory state) -- this either confirms genuine memory exhaustion
       across the containers, or reveals that `web` (or another
       container) had already exited/crashed before this step even ran,
       pointing at a completely different root cause.
    b. If (a) confirms real memory pressure: candidate fixes to evaluate
       (not yet decided) --
         - Reorder/stagger the compose-smoke job so `celery`/`celerybeat`
           don't need to be up during the migration step (does this smoke
           test's actual purpose -- verifying the stack boots and answers
           HTTP -- require them running simultaneously with the
           migration, or could they start afterward?).
         - Check whether `docker-compose.yml`'s existing `deploy.resources.limits`
           (Phase 53's `WEB_CPUS`/`CELERY_CPUS` etc. and their paired
           memory limits) are now tight enough to cause an IN-container
           OOM during a cold-start Django+Wagtail import, independent of
           the runner's own overall budget -- these limits were designed
           around today's default hardware assumptions, not necessarily
           validated against a from-scratch Django import's peak memory.
         - Consider whether `ubuntu-latest`'s standard runner has enough
           headroom at all for a 6-container full-stack smoke test, or
           whether this job needs a larger runner (GitHub offers larger
           hosted runners) -- a cost/complexity tradeoff to raise with the
           user, not something to decide unilaterally.
    c. If (a) shows `web` (or another container) had already crashed
       independently: diagnose that crash on its own terms (`docker
       compose logs web` from that run), not assumed to be memory-related
       just because this phase started from an OOM hypothesis.

  Verify: cannot be verified from this dev box at all -- no live compose
  stack here, and this dev box isn't resource-constrained the same way a
  standard GitHub-hosted runner is, so even a successful local repro
  wouldn't prove anything about the actual failure. Diagnostic step (a)
  must run in real CI and be read from a real log, same discipline as
  every other phase this session -- do not guess past this point.

  STATUS: DIAGNOSTIC STEP ADDED (2026-09-28) -- this phase's deliverable is
  the diagnostic itself, not a fix; root cause remains genuinely open until
  the next CI run's evidence comes back. Added a "Capture resource
  diagnostics before migrations" step (`free -h`, `docker compose ps`,
  `docker stats --no-stream`) immediately before both jobs' "Run Django
  migrations"/"Run Django migrations via compose" steps -- `compose-smoke`
  AND `playwright` (the latter hits the identical pattern once it actually
  runs, currently skipped while `compose-smoke` fails first).
  Correction made during implementation: first added `if: always()` to
  these new steps by reflex (copying the pattern from the pre-existing
  "Collect compose logs on failure"/"Tear down stack" steps nearby) --
  caught and removed before finalizing, since `always()` would make this
  diagnostic run even if an EARLIER, unrelated step had failed, which
  isn't the intent; it should just run in normal sequence like any other
  step. Verified via `python3 -c "import yaml; yaml.safe_load(...)"` that
  the workflow is still valid YAML, both new steps land in the correct
  position in each job's step list, and only the two legitimate
  pre-existing `if: always()` instances remain (the real "Tear down
  stack" steps). Next action: push, wait for the next CI run, read the
  new diagnostic output for real evidence -- then, and only then, decide
  on an actual fix (a follow-up phase, not this one).

----------------------------------------------------------------
Phase 67 -- Fix nginx proxying to a dead `web` container after `make upgrade`
----------------------------------------------------------------
  Trigger: live PDX-CL1 bug, caught immediately after running `make
  upgrade` on my own recommendation (to pick up Phases 60-64's real
  app-code fixes). The upgrade script's own health check failed:

    HEALTH CHECK FAILED after the upgrade. Nothing was rolled back
    automatically -- decide based on 'docker compose logs' first.

  Investigation (real evidence at every step, per this session's
  discipline -- no guessing):
    1. `docker compose logs web --tail 100` on PDX-CL1: gunicorn booted
       clean at 18:43:23 (`Starting gunicorn 26.0.0`, 3 workers, zero
       errors, zero tracebacks).
    2. `docker compose logs nginx --tail 30`: repeated, for 10+ minutes
       straight (18:53:10 onward, while the user was live in the browser
       on the ops page) --
         connect() failed (111: Connection refused) while connecting to
         upstream ... upstream: "http://172.19.0.4:8000/api/gmail/progress"
       -- `111: Connection refused` specifically (not a timeout), meaning
       nothing was listening at that IP at all, not that the app was slow.
    3. `docker compose ps`: `backdeezup-web-1` -- `Up 11 minutes
       (healthy)`. `backdeezup-nginx-1` -- `Up 3 hours`. web was freshly
       recreated by the upgrade; nginx was NOT touched.
    4. `free -h`: 15Gi free / 17Gi total. Ruled out OOM as an explanation
       for anything here.
    5. `docker inspect backdeezup-web-1 --format 'OOMKilled={{.State.OOMKilled}}
       ExitCode={{.State.ExitCode}} Status={{.State.Status}}'`:
       `OOMKilled=false ExitCode=0 Status=running`. web never crashed,
       never restarted, is healthy right now. The 502s are not caused by
       anything wrong with web itself.
    6. Read `scripts/upgrade.sh` (Phase 49) in full: step 3 is
       `docker compose run --rm web python manage.py migrate` then
       `docker compose up -d` -- an IN-PLACE `up -d`, never a `down`
       first. Compose only recreates containers whose image/config
       changed -- `web`/`celery`/`celerybeat` (new image) get recreated
       (new container, new internal Docker network IP); `nginx`/`db`/
       `redis` (unchanged image/config) are left running untouched.
    7. Read `nginx/nginx.conf.template` in full: the only proxy block is
       `location / { proxy_pass http://web:8000; ... }` -- a bare
       hostname, no `resolver` directive anywhere in the file. Stock
       nginx behavior: a bare hostname in `proxy_pass` (not a variable)
       is resolved ONCE, at nginx startup/worker-fork time, and the
       resolved IP is cached in the compiled upstream for that worker
       process's entire lifetime. There is no periodic re-resolution
       without an explicit `resolver` directive + a *variable* in
       `proxy_pass` (a well-documented Docker Compose + nginx gotcha).
       Since nginx itself was never restarted by the upgrade, its workers
       kept the OLD (pre-upgrade, now-dead) `web` container's IP
       (`172.19.0.4` in the logs) forever -- hence permanent `Connection
       refused`, not a transient blip that would clear up on its own.
    8. Checked `make redeploy` in the Makefile for the same bug: it runs
       `docker compose down` BEFORE `docker compose up -d`, which tears
       down and recreates every container including nginx -- nginx always
       gets a fresh DNS lookup on start. `redeploy` is NOT affected. Only
       the in-place `upgrade` path (Phase 49) hits this.

  Immediate live fix (told directly to the user, not a code change --
  restores PDX-CL1 right now without touching data):
    docker compose restart nginx
    curl -ksf https://localhost:18445/health/ && echo OK

  Structural fix (this phase's actual deliverable) -- make nginx
  re-resolve `web`'s IP periodically instead of caching it forever, using
  Docker Compose's built-in embedded DNS server at `127.0.0.11`:

    In nginx/nginx.conf.template, inside the `location /` block, replace:
      proxy_pass http://web:8000;
    with:
      resolver 127.0.0.11 valid=10s ipv6=off;
      set $upstream_web web:8000;
      proxy_pass http://$upstream_web;
    (the `set $upstream_web ...;` + variable in `proxy_pass` is what
    forces nginx to treat this as dynamic and actually honor `resolver`
    -- a bare hostname in `proxy_pass` ignores `resolver` entirely, so
    both pieces are required together, not just adding `resolver` alone.)

  Why this is the right fix and not a bigger one:
    - Fixes the root cause structurally (nginx's DNS caching behavior),
      not just today's specific trigger -- protects against ANY future
      scenario where `web` gets recreated without nginx also recreating
      (a manual `docker compose up -d --no-deps web`, a future deploy
      script, etc.), not only `make upgrade`.
    - No change needed to `scripts/upgrade.sh` or the `Makefile` --
      `upgrade.sh`'s existing health-check loop already retries for up to
      50s (10 attempts x 5s sleep), comfortably past the 10s
      `valid=10s` re-resolution window, so the health check will simply
      pass on its own once this ships, with zero script changes.
    - `valid=10s` matches Docker Compose's own embedded DNS TTL
      conventions (commonly recommended value for this exact pattern);
      `ipv6=off` avoids nginx wasting time on AAAA lookups Docker's
      embedded DNS won't usefully answer for bridge-network service
      names.
    - Scoped to exactly the one `proxy_pass` this template has -- no
      speculative resolver/upstream changes to the other `location`
      blocks (`/static/`, `/media/images/`, `/protected-media/`), which
      are `alias` directives serving files directly from the nginx
      container's own filesystem, not proxying to `web` at all, so they
      cannot exhibit this bug.

  Verify:
    1. `docker compose config -q` (or equivalent template-render check)
       after substituting `${NGINX_HTTPS_PORT}` -- confirms the templated
       nginx.conf is still valid config syntax.
    2. `docker compose exec nginx nginx -t` against the rendered config --
       confirms nginx itself accepts the `resolver`/`set`/`proxy_pass`
       trio (some restricted nginx variants disallow `resolver` outside
       specific contexts; the stock `nginx:stable-alpine` image used here
       does not).
    3. Real local repro of the exact failure mode: start the full stack
       (`make up` or `docker compose up -d`), confirm `/health/` responds,
       then run `docker compose up -d --force-recreate --no-deps web`
       (this reproduces exactly what `upgrade.sh`'s in-place `up -d` does
       to `web` alone, without needing a real image change) -- immediately
       after, confirm nginx logs briefly show the old IP failing (or
       nothing, if timed past the TTL) and then self-heal to 200s within
       ~10s, with NO manual `docker compose restart nginx` needed. This is
       the actual regression test for this bug -- without it, a fix could
       look plausible on paper but not actually resolve on a real
       recreate.
    4. Confirm `location /` still preserves every existing behavior
       (Phase 50's `$http_host` vs `$host` fix, the 360s read/send
       timeouts, the security headers) -- this change only touches how
       the upstream address is resolved, not any other directive in the
       block.

  Not yet applied to PDX-CL1 itself beyond the immediate live
  `docker compose restart nginx` -- the structural template fix ships via
  the normal `git push` + next `make upgrade`/`make redeploy` cycle, same
  as every other phase this session.

  STATUS: DONE (2026-09-28). Applied the `resolver 127.0.0.11 valid=10s
  ipv6=off; set $upstream_web web:8000; proxy_pass http://$upstream_web;`
  change to nginx/nginx.conf.template's `location /` block.

  Verified for real, not on paper:
    1. `nginx -t` against the rendered template (with `${NGINX_HTTPS_PORT}`
       substituted and throwaway self-signed certs mounted, via
       `docker run --rm -v ... nginx:stable-alpine nginx -t`): "syntax is
       ok" / "test is successful".
    2. Actual regression test of the exact bug mechanism, using two
       throwaway nginx containers side by side on a real Docker network
       (no Google secrets needed, so runnable on this dev box despite the
       "no live compose stack" constraint noted in Phase 66 -- that
       constraint was about needing the FULL app stack; this test only
       needed nginx + a plain HTTP server, isolating precisely the piece
       that changed):
         a. `test_nginx_old` running the pre-Phase-67 bare
            `proxy_pass http://web:8000;` (no resolver).
         b. `test_nginx_new` running the Phase 67 resolver+variable
            version.
         c. Both pointed via Docker network alias `web` at a container
            serving "OLD", at a fixed IP (172.30.0.10). Confirmed both
            return "OLD".
         d. Force-recreated the `web`-aliased container at a DIFFERENT
            fixed IP (172.30.0.20, simulating exactly what `docker
            compose up -d` does to `web` during `make upgrade` --
            in-place recreate, new IP, nginx never restarted) serving
            "NEW".
         e. Immediately after: BOTH nginx containers return 504 (the new
            config's cache hasn't hit its 10s TTL yet -- expected, not a
            bug).
         f. 12+ seconds after the recreate: `test_nginx_old` STILL
            returns 504 forever (reproduces the exact PDX-CL1 symptom --
            permanent failure, no self-recovery, matching the real
            10+-minute-and-counting `Connection refused` seen in PDX-CL1's
            actual nginx logs). `test_nginx_new` returns "NEW" -- self-
            healed automatically, zero manual intervention, zero nginx
            restart.
    3. Cleaned up all throwaway test containers/network afterward
       (`test_web1`, `test_web2`, `test_nginx_old`, `test_nginx_new`,
       `backdeezup_test_net`) -- nothing left behind in this dev box's
       Docker state.

  This is about as close to a real regression test as this bug can get
  without the full Google-secrets-dependent app stack: it exercises the
  literal mechanism (Docker embedded DNS caching vs. periodic
  re-resolution under `resolver`) that caused and now fixes the real
  production incident, not a simulated/assumed version of it.

  Remaining: push, then on PDX-CL1 pick this up via the normal
  `make upgrade` cycle (nginx does get recreated by `make redeploy`
  today regardless, and after this fix `make upgrade` no longer needs
  nginx to be recreated at all -- it will self-heal on its own within
  10s of `web` coming back up).

  CORRECTION (2026-09-28, same day): the claim directly above --
  "make upgrade no longer needs nginx to be recreated at all" -- was
  WRONG, disproven by a real second `make upgrade` run on PDX-CL1
  immediately after this commit shipped. The resolver fix only helps
  once nginx has actually LOADED a config containing it; `make upgrade`
  never restarts nginx at all (see Phase 68), so the new template sat on
  disk, unread, while the running nginx container kept using its old,
  pre-Phase-67 in-memory config. The regression test above was real and
  correct for what it tested (DNS caching once the new config is
  running) but didn't cover the actual deploy mechanism that gets nginx
  to load a new config in the first place -- that gap is Phase 68.

----------------------------------------------------------------
Phase 68 -- `make upgrade` must restart nginx to actually load config changes
----------------------------------------------------------------
  Trigger: user ran `make upgrade` on PDX-CL1 a second time, this time
  with Phase 67's nginx.conf.template fix already pulled in via
  `git pull`. Same failure:

    HEALTH CHECK FAILED after the upgrade.

  Investigation:
    1. Re-read the pasted `make upgrade` output's `up 6/6` block closely
       (already-available evidence, no new commands needed this time):
         Container backdeezup-redis-1      Healthy   12.9s
         Container backdeezup-nginx-1      Running   0.0s
         Container backdeezup-db-1         Healthy   12.9s
         Container backdeezup-celery-1     Started   12.1s
         Container backdeezup-web-1        Started   12.4s
         Container backdeezup-celerybeat-1 Started   11.6s
       `nginx-1` at `Running 0.0s` -- distinctly different from every
       other service, all of which show real elapsed work. This is
       Docker Compose's own explicit signal that it took zero action on
       `nginx` -- confirmed already in the compose CLI's own status
       reporting, no extra log-fetching needed to establish this fact.
    2. Read docker-compose.yml's `nginx` service definition in full
       (lines 118-132): `image: nginx:stable-alpine` (no `build:`),
       `volumes: - ./nginx/nginx.conf.template:/etc/nginx/nginx.conf.template:ro`
       (plain bind mount), `command: ["/bin/sh", "-c", "envsubst
       '$$NGINX_HTTPS_PORT' < /etc/nginx/nginx.conf.template >
       /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]`.
    3. This confirms the mechanism precisely: the `envsubst` render step
       is embedded IN the container's startup command, not a separate
       reload-triggering process. It runs exactly once, at container
       start, and never again for the life of that container.
       `docker compose up -d`'s up-to-date check compares each service's
       OWN declared config (image reference, environment map, command
       array, port list, the volumes LIST itself) against what's
       currently running -- none of those changed for `nginx` this
       upgrade (same image, same env, same command string, same mounts
       list), so compose correctly (by its own rules) concluded nginx
       needed no action. It has no mechanism to notice that the BYTES
       inside a bind-mounted file changed -- that's simply out of scope
       for what `docker compose up -d`'s reconciliation checks.
    4. Net result: the already-running nginx container (up for
       hours/days, spanning the ENTIRE Phase 67 deploy) kept serving
       whatever `/etc/nginx/nginx.conf` it rendered at its actual last
       real start -- a config from before Phase 67 existed, with no
       resolver directive at all. Phase 67's fix was correctly written,
       correctly committed, correctly pulled onto PDX-CL1's disk -- and
       never once loaded into a running nginx process.

  Immediate live fix applied (not a code change): `docker compose
  restart nginx` -- forces the container to actually exit and restart,
  which re-runs its `command`, which re-runs `envsubst` against the
  NOW-current template on disk, which finally loads Phase 67's resolver
  fix for real.

  Real fix (this phase's deliverable): make `scripts/upgrade.sh`
  unconditionally force nginx to restart/recreate as part of every
  upgrade, immediately after (or as part of) the main
  `docker compose up -d` step -- e.g.:
    docker compose up -d --force-recreate nginx
  or equivalently `docker compose restart nginx` right after `up -d`.
  This guarantees:
    - Any future `nginx.conf.template` edit always takes effect on the
      very next `make upgrade`, with no silent gap between "the fix is
      on disk" and "the fix is actually running" ever again.
    - nginx also gets a guaranteed-fresh DNS resolution of `web`
      immediately on every upgrade, belt-and-suspenders with Phase 67's
      10s self-heal -- not a replacement for Phase 67, since Phase 67
      still matters for `web` recreates that happen OUTSIDE of
      `upgrade.sh` entirely (e.g. someone running `docker compose up -d
      --no-deps web` by hand, where nothing restarts nginx proactively
      at all and the 10s resolver self-heal is the only thing that saves
      it).
  Why not instead rely on `docker compose up -d --force-recreate` for
  ALL services every upgrade (simpler-sounding, one flag): rejected --
  that would also force-recreate `db`/`redis` unnecessarily on every
  single upgrade even when their images/config are unchanged, which is
  wasteful at best and, for `db` specifically, needlessly increases the
  blast radius of every upgrade for a container that legitimately never
  needs to restart just because `web` or `nginx` changed. Scoping
  `--force-recreate` to `nginx` alone (and letting compose's normal
  image-diff-driven behavior handle `web`/`celery`/`celerybeat` as it
  already correctly does) is the minimal targeted fix.

  Verify: this dev box has no live PDX-CL1-equivalent compose stack
  running (same constraint as Phases 66/67), but the actual mechanism
  under test here -- "does `docker compose up -d` restart a service when
  only a bind-mounted file's contents change, and does `--force-recreate
  <service>` fix that" -- doesn't require the real Django app, Google
  secrets, or Postgres at all, so it can be verified the same way Phase
  67's regression test was: a minimal docker-compose.yml with one
  service bind-mounting a text file rendered by its `command`, edit the
  file, run plain `up -d` and confirm no restart happens (reproduces the
  bug), then run `up -d --force-recreate <service>` and confirm the file
  IS re-rendered (proves the fix). Then apply the equivalent line to the
  real `scripts/upgrade.sh`.

  STATUS: DONE (2026-09-28). Added
    run "Restarting nginx to pick up any config changes" \
      docker compose up -d --force-recreate nginx
  to scripts/upgrade.sh immediately after "Starting the updated stack"
  (`docker compose up -d`), before the dry-run early-exit check (so
  `--dry-run` correctly prints "[dry-run] would run: ..." for this step
  too, via the existing `run()` helper's own dry-run guard -- no new
  dry-run handling needed).

  Verified for real, not on paper: `bash -n scripts/upgrade.sh` (syntax
  OK), plus a minimal real repro of the exact mechanism (no Google
  secrets needed, same approach as Phase 67's verification) -- a
  throwaway one-service compose stack (`python:3.12-slim`) bind-mounting
  a text file and copying it to an output file via its `command` at
  container start, standing in for nginx's `envsubst` render:
    1. Started it, confirmed the output file read "OLD" (initial
       template content).
    2. Edited the bind-mounted file to "NEW", ran plain
       `docker compose up -d` -- compose reported the container as
       `Running` (no recreate), output file STILL read "OLD". This is
       the exact bug, reproduced mechanically, not assumed.
    3. Ran `docker compose up -d --force-recreate renderer` -- compose
       reported `Recreate` / `Recreated` / `Starting` / `Started`, output
       file now read "NEW". This is the exact fix, proven to work, not
       assumed.
    4. Cleaned up (`docker compose down -v`), nothing left behind.

  This directly proves the mechanism `scripts/upgrade.sh`'s new line
  depends on: plain `up -d` is a genuine no-op for a service whose only
  change is a bind-mounted file's contents, and `--force-recreate
  <service>` is what actually forces that service to re-run its startup
  command and pick the change up.

  Also corrects Phase 67's runbook (see the CORRECTION note added there
  same day): Phase 67's resolver fix was real and independently verified
  correct, but it could never have taken effect on PDX-CL1 without this
  phase, since nginx was never being restarted at all to load it.

  Remaining: push, then PDX-CL1 needs ONE more `make upgrade` run using
  a checkout that already has THIS commit (or the immediate manual
  `docker compose restart nginx` workaround already given for right now)
  to actually load Phase 67's resolver fix for the first time -- every
  `make upgrade` after that point will handle it automatically via this
  phase's new step.

----------------------------------------------------------------
Phase 69 -- Fix dry-run preview ignoring rule conditions
----------------------------------------------------------------
  Trigger: not a user bug report -- found while reading
  backend_django/google_gmail_backup/services_rules.py and query_compiler.py
  to ground Phase 70's design (user asked for "an agent to go through my
  mail from the database side using the API to build and improve
  existing rules"). Investigating how existing rules actually execute
  surfaced this independently.

  Investigation (real code reads, exact line numbers, not guessed):
    1. backend_django/google_gmail_backup/models.py:275-283 --
       RuleCondition.Field already includes CATEGORY, compiling (per
       query_compiler.py:74-78) to Gmail's native `category:promotions`
       search syntax. This DISPROVED my original Phase 70 premise
       ("backfill labelIds so category becomes usable") -- category
       filtering already exists at the model/compiler layer.
    2. backend_django/google_gmail_backup/api.py:597-618 (create_rule
       endpoint) -- confirms `rule.gmail_query` is NOT a separate,
       independently-typed field: it's compiled from the submitted
       RuleCondition list via `query_compiler.compile_conditions()` and
       persisted as `gmail_query` at rule-creation time. So
       `rule.gmail_query` is the authoritative representation of a
       rule's full condition set.
    3. backend_django/google_gmail_backup/services_rules.py:113-183
       (apply_rule) -- read the FULL function, not just the part that
       looked relevant:
         - Line ~145-151 (dry-run count path): `qs = GmailMessage.objects
           .select_for_update(skip_locked=True).filter(state=VERIFIED,
           date__lte=cutoff).exclude(deleted_at__gte=recent_cutoff)` --
           then protected-sender/attachment excludes, then
           `total_count = qs.count()`. NO reference to `rule.gmail_query`
           or `RuleCondition` anywhere in this branch.
         - Line ~165-177 (only reached when `not dry_run`): builds
           `matching_ids` by paging through
           `svc.users().messages().list(q=rule.gmail_query, ...)` against
           the LIVE Gmail API, then `qs = qs.filter(gmail_id__in=
           matching_ids)` -- THIS is where sender/subject/category/label
           conditions actually take effect. It is explicitly gated
           `if not dry_run and rule.gmail_query.strip():` -- dry-run
           never reaches it.
         - The existing code comment directly above this block says:
           "For dry-run: count from local DB only (fast, no Gmail API
           call) / For real run: also cross-reference live Gmail query to
           catch label changes" -- confirming this asymmetry was a
           deliberate original design choice (a speed optimization),
           not an oversight introduced later -- but one that silently
           broke the accuracy guarantee Phase 34 depends on.
    4. Cross-checked against Phase 34's actual safety gate:
       `dry_run_confirmation_error()` (services_rules.py:34-49) blocks
       the Execute UI path unless `confirm_count == rule.last_dry_run_count`
       and the dry run is under 24h old. `rule.last_dry_run_count` is set
       at services_rules.py:187-188 directly from the (currently
       inaccurate) `total_count` computed in step 3's dry-run branch.
       So the gate is real and does fire -- it's just gating against the
       wrong number for any rule with a real condition.

  Concrete failure scenario this produces: create a rule "category:
  promotions AND older_than:30d, action=trash". Dry run shows, say,
  "1,400 messages" (every VERIFIED message older than 30 days, rule
  ignored). Execute (after the 24h/count-match gate passes on that wrong
  number) actually only trashes the ~80 that are genuinely in
  CATEGORY_PROMOTIONS. Not data-lossy in this direction (real run is
  narrower than what dry-run promised) -- but the INVERSE is also
  possible and IS data-lossy: a rule with a condition that WIDENS what
  Gmail's live search matches versus the local age-only filter (e.g. a
  condition that has nothing to do with age at all, or Gmail search
  syntax matching messages the local `date__lte=cutoff` filter would
  have excluded) could execute against MORE messages than the dry run
  ever showed the user, with the confirmation count gate having approved
  a completely unrelated number. The gate's entire purpose -- "you saw
  this preview, you approved this count" -- is violated either direction.

  Fix (this phase's deliverable): remove the `if not dry_run` guard on
  the live-Gmail-query cross-reference block so it runs whenever
  `rule.gmail_query.strip()` is non-empty, REGARDLESS of dry_run. The
  existing `if dry_run: <count and return> else: <execute batch loop>`
  split, which comes AFTER that point in the function, continues to be
  the only thing that decides whether real trash/star/label/archive API
  calls fire. Net diff is small: hoist the `svc = gmail_service(); ...
  matching_ids ...; qs = qs.filter(gmail_id__in=matching_ids)` block
  above the `if dry_run:` branch instead of inside an `if not dry_run:`
  wrapper.

  Rejected alternative (local ORM filter mirroring Gmail syntax):
  considered building a parallel compiler that translates
  RuleCondition rows into Django ORM `Q()` filters against `GmailMessage`
  fields directly (`from_email_normalized__icontains`, `subject__icontains`,
  `labels__contains`, etc.) instead of calling live Gmail at all, even
  for real runs. Rejected for two concrete reasons found in code, not
  hypothetical: (a) `labels` (google_gmail_backup/management/commands/
  gmail_pipeline.py:125) is only populated `if not msg.subject and not
  msg.from_address` -- i.e. only for messages that had no metadata
  cached from search-time snippets, NOT backfilled for the bulk of
  already-downloaded mail -- so a local CATEGORY filter would silently
  under-match against real Gmail state; (b) Gmail's search operators
  (`subject:`, quoted-phrase handling, `category:`, `older_than:`) have
  their own matching semantics that a hand-rolled Python equivalent would
  have to reverse-engineer and keep in permanent sync with Google's
  actual behavior -- a real, ongoing drift risk. Reusing the exact same
  live-query code path for both dry-run and real-run has zero drift risk
  by construction (it's the same code, not a parallel implementation).

  Honest tradeoff to document, not hide: dry-run now costs one live
  Gmail API call per rule (previously zero, per the removed "fast, no
  Gmail API call" comment) and requires valid Gmail auth even to preview
  a rule, not just to execute it. Accepted: this is the literal thing
  Phase 34's safety gate exists to guarantee, and a preview that doesn't
  reflect reality isn't actually a safety feature.

  Verify:
    1. Read the affected test files first (tests_cleanup_safeguards.py,
       tests_regression.py, tests_undo_protect.py, tests.py) to find
       existing dry-run/execute-count assertions and confirm none assume
       the OLD (buggy) "dry-run never calls Gmail" behavior in a way that
       would now break -- if any do (e.g. asserting zero Gmail API mock
       calls during a dry run), update them to reflect the corrected
       contract rather than working around the fix.
    2. Add/extend a test: create a CleanupRule with a real
       RuleCondition (e.g. sender-restricted, not just age), mock the
       Gmail service's `messages().list()` to return a known subset,
       assert dry-run's `total_count`/`affected_gmail_ids` now matches
       exactly what that mocked live query returns intersected with the
       local age/protected/attachment filters -- not just every
       VERIFIED+aged message.
    3. Run the scoped test files locally with `DATABASE_URL=` cleared
       (forces SQLite, matches CI) -- per this repo's standing
       never-run-the-full-suite-on-this-dev-box constraint.

  STATUS: DONE (2026-09-28). Edited services_rules.py:
    - Removed the `not dry_run` gate on the live-Gmail-query
      cross-reference block (was `if not dry_run and rule.gmail_query
      .strip():`, now `if rule.gmail_query.strip():`), with an updated
      comment explaining why (Phase 69, dry-run now costs one live Gmail
      API call, trades speed for the preview actually being accurate).
    - Updated the stale "Dry-run: count from DB only (no Gmail API,
      fast)" comment on the count line to reflect that `qs` now already
      incorporates `rule.gmail_query` filtering by that point.

  Verified for real, not on paper:
    1. Grepped every test file for `gmail_query=` to find any existing
       rule fixture with a non-empty query that dry-run tests rely on --
       found ONE: tests_regression.py's `CleanupRuleRatelimitTest`
       (`gmail_query="from:newsletter"`), calling dry-run endpoints
       WITHOUT mocking `gmail_service`. Read `gmail_service()`
       (services_gmail.py:20-31) to confirm it returns `None` gracefully
       (not an exception) when no credentials exist -- matches this dev
       box's "no Google network" constraint -- so the existing `if svc:`
       guard already handles this cleanly with no test changes needed.
    2. Ran the full previously-passing suite after the fix:
       `google_gmail_backup.tests_regression.CleanupRuleRatelimitTest` +
       `tests_reconciliation` via `manage.py test` (11/11 passed) and
       `tests_cleanup_safeguards.py` + `tests_undo_protect.py` via
       `pytest` (these are pytest-native files -- confirmed `manage.py
       test` finds 0 tests in them, same discovery gap Phase 63 already
       documented; ran them the correct way) -- 31/31 passed (29
       pre-existing + 2 new).
    3. Added two new regression tests to tests_cleanup_safeguards.py:
       `test_dry_run_applies_gmail_query_not_just_age` (two equally-old
       messages, only one matches a mocked live Gmail search -- asserts
       dry-run now reports exactly that one, and that `gmail_service()`
       was actually called) and
       `test_dry_run_skips_gmail_query_call_when_query_is_empty` (the
       default age-only `rule` fixture must NOT call `gmail_service` at
       all -- no behavior change for the common case).
    4. Proved the new test is a REAL regression test, not a false
       positive: `git stash`'d just services_rules.py (reverting to the
       pre-fix code) and re-ran
       `test_dry_run_applies_gmail_query_not_just_age` alone --
       confirmed it FAILS against the old code (`1 failed`) -- then
       `git stash pop` to restore the fix and confirmed it passes again.
    5. `ruff check` on both changed files: all checks passed.

  This closes the exact gap identified: dry-run's preview count/sample
  now comes from the SAME filtered queryset the real run would use
  (age + protected-sender + attachment excludes + live Gmail query, when
  set), so Phase 34's dry-run-must-match-before-execute gate is now
  checking an accurate number.

----------------------------------------------------------------
Phase 70 -- Mine FOSS spam-rule corpora to seed suggested cleanup rules
----------------------------------------------------------------
  Trigger: user request -- "i need an agent to go through my mail (from
  the database side) using the api to build and improve existing rules
  like a feedback / enhancement cycle." Explicit instruction: search the
  internet first, ensure FOSS, before building anything.

  FOSS research performed (WebSearch + verification via `gh api` reading
  actual LICENSE file bytes, never trusting a repo blurb or GitHub's
  auto-detected license badge alone):
    - Apache SpamAssassin (apache/spamassassin) -- confirmed Apache-2.0
      via `gh api repos/apache/spamassassin --jq '.license.spdx_id'`.
      Decades of community-maintained heuristic rules (`.cf` files:
      header regex, body phrase, phishing patterns, scored and
      combined) plus the public SpamAssassin Mail Corpus (labeled
      spam/ham email dataset).
    - Rspamd (rspamd/rspamd) -- GitHub's own license badge returned
      NOASSERTION (would have wrongly read as "unlicensed"). Listed the
      repo root (`gh api repos/rspamd/rspamd/contents/`), found the
      actual file is `LICENSE.md` (not `LICENSE`), read its content
      directly -- genuinely Apache License 2.0 full text. A real
      false-negative in GitHub's auto-detection, only caught by reading
      actual bytes instead of trusting the badge.
    - martinschaible/rspamd-rules (MIT, verified), kawaiipantsu/
      spamassassin-rules (MIT, verified) -- community rule packs, extra
      corroborating prior art.
    - Elie222/inbox-zero -- 12.4k stars, closest FEATURE match (layered
      deterministic-rules-then-AI matching, explicit correction-based
      feedback loop) but license is AGPLv3 PLUS added terms read
      directly from the LICENSE file: no monetizing the software, and
      any org with 5+ business users needs a paid enterprise license.
      That's source-available, not OSI-compliant FOSS -- ruled out per
      the user's explicit "ensure is FOSS" requirement, despite being
      the best feature match. Good pattern to borrow (deterministic
      rules first, AI proposes, human approves), bad license to build on.
    - sohaib-0897/InboxLearn -- exactly the "feedback/enhancement cycle"
      shape (human corrections -> isolated candidate model -> gated
      eval -> rollback) but has NO license file at all ("all rights
      reserved" by default copyright) -- cannot legally reuse the code,
      cited only as a design pattern, not a dependency.
    - dmarchevsky/gmail-triage, jikahu/gmail-intelligence-agent -- also
      unlicensed, ruled out for the same reason.

  Scope correction (see chat with user, not silently absorbed): the
  original plan item #1 ("backfill Gmail's labelIds/category into the
  DB so rules can use Google's own classification") turned out to
  already be implemented -- see Phase 69's investigation:
  `RuleCondition.FIELD_CATEGORY` already exists and already compiles to
  `category:X` Gmail search syntax, already sent to the live Gmail API
  during real rule execution. Told the user directly rather than writing
  up a redundant phase. This phase (70) is now scoped to ONLY the
  genuinely missing piece: signals Gmail's own classifier does not
  expose as a queryable rule field at all.

  Design (grounded in what already exists in this codebase, not
  invented from scratch):
    - Every DOWNLOADED/VERIFIED GmailMessage already has its full raw
      RFC822 saved locally at `GmailMessage.raw_path` (written during
      the download step, google_gmail_backup/management/commands/
      gmail_pipeline.py). This makes the analysis genuinely "from the
      database side" as the user asked -- parse headers from the LOCAL
      .eml files already on disk via Python's stdlib `email` module (or
      `email.parser.BytesParser`), no additional Gmail API calls needed
      for the analysis pass itself. The Gmail API is only touched later,
      IF a human accepts a suggestion and it becomes a real rule (same
      existing create_rule path, which already talks to Gmail to fetch/
      create labels etc.).
    - Header-heuristic signals to extract per message, using
      SpamAssassin/Rspamd's rule catalogs as the starting PATTERN list
      (the ideas, not their code or DSL -- their rule engines operate at
      SMTP/MDA time on raw messages with their own scoring language,
      which doesn't transfer to a Gmail-archive cleanup tool):
        - `List-Unsubscribe` / `List-Unsubscribe-Post` presence (RFC
          2369/8058) -- strong bulk-mail signal.
        - `List-Id` presence -- mailing-list membership.
        - `Precedence: bulk` / `Precedence: list` header.
        - `From` domain vs `Reply-To` domain mismatch -- common
          marketing/phishing pattern SpamAssassin scores heavily.
        - `Return-Path` domain vs `From` domain mismatch.
    - New read-only Django management command (name TBD at
      implementation time, e.g. `analyze_mail_patterns`) that:
        1. Iterates DOWNLOADED/VERIFIED GmailMessage rows with a
           non-empty `raw_path`.
        2. Parses each .eml's headers for the signals above.
        3. Groups by sender domain (reusing the existing
           `from_email_normalized` field already indexed on the model).
        4. For each cluster, checks whether it's already matched by an
           ENABLED CleanupRule's compiled `gmail_query` (reuse the
           SAME live-Gmail-query mechanism Phase 69 makes trustworthy --
           this is exactly why Phase 69 needs to land first) -- clusters
           already covered are excluded from suggestions.
        5. Ranks remaining clusters by message count and writes/updates
           `SuggestedRule` rows (new lightweight model: sender_pattern,
           signal_type, message_count, sample_subjects, first_seen,
           dismissed default False, created_rule FK nullable) --
           idempotent re-run: update counts on existing undismissed
           suggestions rather than duplicating rows.
    - Surface suggestions for human review (exact UI TBD at
      implementation time -- likely a new admin list view or an
      ops.html panel reusing existing patterns, NOT decided yet, needs a
      design pass, not guessed here).
    - NEVER auto-creates or auto-enables a CleanupRule from a
      suggestion. Accepting a suggestion routes through the EXISTING
      create_rule API (api.py:597) exactly as if the user had typed the
      conditions in by hand -- same Phase 34 dry-run-required safety
      gate applies to anything created this way, no bypass.
    - Explicit non-goals for this phase (avoiding premature scope): no
      Bayesian/ML classifier, no training on the old public spam corpora
      (SpamAssassin Public Corpus / Enron / TREC / Ling-Spam) -- these
      are 2000s-era datasets, not representative of 2026 bulk mail
      patterns, not worth the effort versus header heuristics; no
      auto-execution of suggestions ever.

  Depends on: Phase 69 landing first -- this phase's "already covered by
  an enabled rule" check reuses the live-Gmail-query cross-reference,
  which is only trustworthy after Phase 69's fix (otherwise this phase
  would inherit the same preview-vs-reality mismatch when checking
  coverage).

  Verify: entirely read-only by construction (no Gmail API writes, no
  rule auto-creation, no DB writes beyond the new SuggestedRule table) --
  run the new command against a small fixture set of .eml files with
  known List-Unsubscribe/Precedence/domain-mismatch headers (synthetic,
  not real user mail, per the No Invented Data Rule for anything beyond
  clearly-labeled test fixtures), confirm expected sender clusters and
  counts, confirm a sender already covered by an existing enabled rule
  is correctly excluded, confirm re-running is idempotent (no duplicate
  SuggestedRule rows, counts update in place).

  STATUS: DONE (2026-09-28).

  Design change made during implementation (an improvement, not scope
  creep -- see reasoning below): the "already covered by an enabled
  rule" check does NOT reuse the live-Gmail-query mechanism as originally
  planned. Instead it queries `RuleCondition.objects.filter(rule__enabled
  =True, field=FIELD_SENDER)` directly -- fully local, no Gmail API call,
  no auth required to run this command at all. Reasoning: the structured
  RuleCondition rows already say exactly which sender domains an enabled
  rule targets; re-deriving that from a compiled `gmail_query` string (or
  worse, re-executing it live against Gmail) would be strictly more
  complex, slower, and dependent on Gmail auth for what's supposed to be
  a read-only local analysis tool -- for zero accuracy benefit, since the
  RuleCondition rows ARE the source of truth `gmail_query` was compiled
  from in the first place (Phase 69's own finding, api.py:597-618). This
  also means Phase 70 doesn't strictly depend on Phase 69 having landed
  -- moot here since 69 already shipped first, but noted for accuracy.

  Implementation:
    - New model `SuggestedRule` (models.py) -- sender_domain, signal_type
      (5 choices: list_unsubscribe, list_id, precedence_bulk,
      reply_to_mismatch, return_path_mismatch), message_count,
      sample_sender, sample_subjects, first_seen, last_updated,
      dismissed, created_rule (FK to CleanupRule, nullable). Unique
      constraint on (sender_domain, signal_type) for idempotent re-runs.
      Migration: 0013_suggestedrule.py.
    - New read-only management command `analyze_mail_patterns.py`:
      iterates GmailMessage rows with state=VERIFIED and a non-empty
      raw_path, parses each .eml's headers via stdlib `email
      .message_from_bytes` (List-Unsubscribe, List-Id, Precedence,
      Reply-To/Return-Path vs From domain), groups by sender domain
      (via `email.utils.parseaddr`), skips domains already covered by an
      enabled rule (see design change above), skips domains whose
      existing suggestion was dismissed (does not resurface or bump its
      count), upserts the rest via `update_or_create` keyed on
      (sender_domain, signal_type). `--limit` option (default 20000).
      Prints a scan summary (scanned/missing-file/already-covered counts,
      new/updated/dismissed-untouched suggestion counts).
    - New `SuggestedRuleAdmin` (admin.py): read-only list/detail (no add
      permission -- suggestions only come from the command), two bulk
      actions -- "Dismiss selected" and "Create a draft CleanupRule
      (disabled) from selected". The create-draft action builds a
      CleanupRule with `enabled=False, dry_run_default=True` (same
      safe-by-default posture as seed_smart_rules.py's hand-authored
      rules) plus one RuleCondition (sender contains the domain),
      compiles `gmail_query` via the EXISTING `query_compiler
      .compile_conditions()` (the same function api.py's create_rule
      endpoint uses) rather than duplicating that logic, links
      `created_rule` back onto the suggestion, and marks it dismissed
      (resolved). NEVER calls the Gmail API, never sets enabled=True.
    - `Makefile`: added `analyze-mail-patterns: docker compose exec web
      python manage.py analyze_mail_patterns $(ARGS)`, matching the
      existing `seed-smart-rules`/`cleanup-dry` pattern.
    - `.github/workflows/ci.yml`: added the new
      `tests_analyze_mail_patterns.py` file to the Phase 63 pytest-native
      step's file list -- WITHOUT this, per Phase 63's own finding, the
      new tests would silently never run in CI at all (manage.py test's
      unittest-only discovery finds 0 tests in a pytest-native file, and
      the pytest step only runs an explicit file list, not a glob).

  Verified for real, not on paper:
    1. `makemigrations` generated exactly one migration
       (0013_suggestedrule.py, CreateModel only) -- read it to confirm no
       unexpected schema changes.
    2. New test file `tests_analyze_mail_patterns.py` (9 pytest-native
       tests, following tests_cleanup_safeguards.py's established style):
       List-Unsubscribe/Precedence:bulk/Reply-To-mismatch detection each
       create the expected suggestion; a plain message with no signal
       headers creates nothing; a domain already covered by an enabled
       rule's sender condition is correctly skipped (built a real
       CleanupRule+RuleCondition in the test, not mocked); re-running
       against a second message from the same domain updates the
       existing row's count to 2 rather than duplicating; dismissing a
       suggestion then feeding it more matching mail leaves it
       untouched (still dismissed, count NOT bumped); a GmailMessage
       whose raw_path points to a file that doesn't exist is skipped
       gracefully (no crash, correct skip-count in the summary output);
       the admin's create_draft_rule action produces a disabled,
       dry-run-default rule with a compiled gmail_query containing the
       domain and a real RuleCondition row, and marks the source
       suggestion dismissed. All 9 passed.
    3. Ran the FULL existing pytest-native suite (all 6 files from Phase
       63/69 plus the new 7th) together: 76/76 passed.
    4. `ruff check` on every new/changed file: all checks passed.
    5. `python3 -c "import yaml; yaml.safe_load(...)"` on ci.yml: valid.
    6. `manage.py check`: "System check identified no issues" -- confirms
       the new model/admin registration doesn't break app startup.
    7. `uvx bandit` (ephemeral, matches CI's SAST tool without adding a
       project dependency) on the 3 new/changed Python files: "No issues
       identified", exit 0 -- relevant given this command reads
       arbitrary local file paths (raw_path) and parses their bytes as
       email headers.

  Explicit non-goals honored, not silently dropped: no Bayesian/ML
  classifier, no training on old public spam corpora, no auto-creation
  or auto-enabling of a CleanupRule anywhere in the code path -- the
  create_draft_rule action always leaves `enabled=False` and always
  requires a human to click it in the first place.
