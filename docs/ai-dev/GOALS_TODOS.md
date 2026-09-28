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

PHASE 50 -- Fix OAuth redirect_uri behind reverse proxy (browser flow)
  Size: S.  Risk: low (settings + nginx/Caddy config only, no schema/data changes,
  no behavior change for the unaffected `make auth` CLI flow).

  Root cause (confirmed by reading the actual code, not guessed):
    - `backend_django/core/oauth.py` builds the OAuth redirect_uri via
      `request.build_absolute_uri(reverse("oauth_callback"))` on both the start
      and callback legs -- fully dynamic, derived from what Django thinks the
      current request's scheme/host/port are.
    - `nginx/nginx.conf`'s `location /` sends `proxy_set_header Host $host;` --
      nginx's `$host` variable strips any port from the original Host header, so
      Django's HTTP_HOST arrives as e.g. `localhost` with no port at all,
      regardless of what port nginx itself is actually listening on.
    - `backend_django/config/settings.py` never sets `SECURE_PROXY_SSL_HEADER` or
      `USE_X_FORWARDED_HOST`, even though nginx already sends
      `X-Forwarded-Proto: https` (`nginx.conf` line ~58). Django ignores that
      header without those settings, so `request.is_secure()` is False and
      `request.scheme` defaults to `http`.
    - Net effect: the redirect_uri actually sent to Google ends up something like
      `http://localhost/oauth/callback` -- wrong scheme, no port -- which won't
      match whatever's registered as an authorized redirect URI in Google Cloud
      Console for this client. Google shows its generic, unhelpful "Something
      went wrong / Sorry, something went wrong there. Try again." page right
      after the user approves scopes.
    - This is **not** host/port-specific -- it would break identically at the
      documented default (nginx on 8445) exactly as it did on a host running
      nginx on a remapped port (18445). Found 2026-09-27 debugging a real
      install on a second machine (unrelated port-conflict investigation
      surfaced it as a side effect).
    - The CLI `make auth` flow (`google_media_backup`/`google_gmail_backup`
      management commands) is a **separate code path** with no
      request-based redirect_uri construction -- confirmed unaffected, and is
      the working fallback in the interim.

  Fix:
    1. `backend_django/config/settings.py`: add
       `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` and
       `USE_X_FORWARDED_HOST = True`. Standard Django guidance for exactly this
       deployment shape (app only ever reachable through a proxy that sets
       X-Forwarded-Proto) -- note in a comment that this trusts nginx/Caddy as
       the sole entry point, consistent with BIND_ADDR defaulting to
       127.0.0.1 (Phase 39); don't silently weaken that assumption elsewhere.
    2. `nginx/nginx.conf`: change `proxy_set_header Host $host;` to
       `proxy_set_header Host $http_host;` in the HTTPS server block's
       `location /` (`$http_host` preserves the port the client actually
       connected on; `$host` does not). Only that one location block proxies to
       `web` -- the HTTP 80 block just redirects to HTTPS and doesn't need this.
    3. Check `Caddyfile` (Phase 48) for the same class of bug before assuming
       it's fine -- Caddy's `reverse_proxy` forwards the original Host header
       and sets X-Forwarded-Proto automatically by default, so it may already be
       correct, but verify rather than assume.
    4. Check `docs/authentication.md` and README's "Connect Google" section for
       any claim that the browser OAuth flow works today -- correct if it
       overstates it.

  Verify: this can be checked without live Google network access (no Google
  network from vertex-dev -- see memory). Use Django's RequestFactory (or the
  test client) to simulate exactly the headers nginx now sends
  (`X-Forwarded-Proto: https`, `Host: <host>:<port>` as `$http_host` would send
  it) against the oauth-start view, and confirm `request.build_absolute_uri(...)`
  / the actual redirect_uri passed to the Google auth flow now comes out as
  `https://<host>:<port>/...` -- not by hitting Google, by inspecting what the
  app itself constructs. A scoped test file for this (e.g.
  `core/tests_oauth_redirect.py`) is reasonable given Phase 6's per-view-test
  convention.

PHASE 51 -- Fix gmail-loop infinite-retry on permanently-gone messages
  Size: S.  Risk: low (one code path, additive state-transition logic only, no
  schema/migration changes -- GmailMessage.state/deleted_at/deletion_source
  already exist and are already used this exact way elsewhere).

  Root cause (confirmed live, on a real account with 57,895 discovered messages,
  not guessed): `backend_django/google_gmail_backup/management/commands/
  gmail_pipeline.py`'s `_download()` -> `_process(msg)` inner function, on any
  exception, only does:
    msg.error = str(exc); msg.last_attempt_at = timezone.now(); msg.save(...)
  It never touches `msg.state`. A message stays STATE_DISCOVERED forever, even
  when the failure is Gmail itself confirming the message no longer exists
  (`HttpError 404 ... reason: notFound` on `messages.get`). Since `_download`'s
  query is `GmailMessage.objects.filter(state=STATE_DISCOVERED)
  .order_by("discovered_at")[:limit]`, the *same* oldest dead messages get
  re-selected on every single invocation -- `make gmail-loop` (a bash loop
  calling this repeatedly until the DISCOVERED queue is empty) can never
  progress past them to the remaining, actually-downloadable messages behind
  them in discovered_at order. Reproduced live: a 500-message batch was 100%
  404/notFound, loop made zero forward progress.

  `task_gmail_reconcile` (`tasks.py`) already has the exact right handling for
  this signal -- `_mark_soft_deleted(gmail_id, source, now)` on a confirmed 404
  -- but it only scans `state__in=[VERIFIED, DOWNLOADED]`, never `DISCOVERED`,
  so it does not help this case.

  Fix:
    1. In `_process(msg)`'s exception handler, detect a confirmed-permanent
       failure -- `HttpError` with `.resp.status == 404` (preferred, exact) or
       the existing string-matching fallback already used elsewhere in this
       file (`"404" in exc_str or "notFound" in exc_str`) if the raised
       exception type varies by call site. On that specific signal, call the
       existing `_mark_soft_deleted(msg.gmail_id, "gmail_404_on_download",
       timezone.now())` from `google_gmail_backup.tasks` instead of just
       setting `error` -- reuse the proven helper, don't reinvent it.
    2. Every other exception type (network errors, "Empty raw response",
       rate limits, etc.) keeps today's exact behavior -- `error` +
       `last_attempt_at` set, state unchanged, eligible for retry on the next
       loop pass. Do NOT invent a general retry-limit/backoff system here --
       that's a separate, bigger feature; out of scope for this fix. Note it
       in GOALS.md's NOT PHASED backlog if it turns out other error types also
       get permanently stuck in real-world use (unconfirmed as of this
       writing -- only the 404 case has been proven to actually happen).
    3. `docs/operations.md` / `docs/troubleshoot`-style docs: if `make
       gmail-loop` looks stuck at a high err count with no progress, this is
       now a known, self-resolving situation (the fix skips past confirmed-gone
       messages automatically) rather than something to manually intervene on
       -- add a line to the Troubleshooting table if one doesn't already cover
       "0 downloaded, all errors."

  Verify: `core/tests_gmail_download_404.py` or extend an existing
  `google_gmail_backup/tests_*.py` file (check what exists first) --
  mock `get_message_raw`/the Gmail service call to raise an `HttpError`-shaped
  404, call `_process`/the download path, and assert the message ends up
  `STATE_SOFT_DELETED` with `deletion_source="gmail_404_on_download"` and
  `deleted_at` set -- not left in `DISCOVERED`. Also assert a non-404 exception
  (e.g. a plain `ConnectionError`) leaves state unchanged (regression guard for
  point 2 above, so a future change doesn't accidentally soft-delete on
  transient errors). No live Google network needed -- mock-based, same
  constraint as every other Google-API test in this repo.
