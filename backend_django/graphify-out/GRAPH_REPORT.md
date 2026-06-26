# Graph Report - backend_django  (2026-06-26)

## Corpus Check
- 93 files · ~41,293 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 795 nodes · 1338 edges · 79 communities (55 shown, 24 thin omitted)
- Extraction: 71% EXTRACTED · 29% INFERRED · 0% AMBIGUOUS · INFERRED: 386 edges (avg confidence: 0.57)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bac0f694`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]

## God Nodes (most connected - your core abstractions)
1. `GmailMessage` - 44 edges
2. `CleanupRule` - 42 edges
3. `GmailSyncState` - 41 edges
4. `ProtectedSender` - 37 edges
5. `RuleCondition` - 28 edges
6. `apply_rule()` - 28 edges
7. `CleanupAuditLog` - 26 edges
8. `gmail_service()` - 22 edges
9. `VaultMedia` - 21 edges
10. `GmailAttachment` - 17 edges

## Surprising Connections (you probably didn't know these)
- `export_assets()` --calls--> `export_queryset()`  [INFERRED]
  google_media_backup/api.py → google_gmail_backup/exports.py
- `task_docs_import_vault()` --calls--> `VaultDocument`  [INFERRED]
  google_media_backup/tasks.py → media_vault/models.py
- `Command` --uses--> `DriveAsset`  [INFERRED]
  media_vault/management/commands/import_media.py → google_media_backup/models.py
- `Command` --uses--> `GmailAttachment`  [INFERRED]
  media_vault/management/commands/import_media.py → google_gmail_backup/models.py
- `gmail_service()` --calls--> `_load_creds()`  [INFERRED]
  google_gmail_backup/services_gmail.py → google_media_backup/services_google.py

## Communities (79 total, 24 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (51): AbstractDocument, AbstractImage, AbstractMedia, AbstractRendition, Command, _guess_mime(), Import pipeline: scan backed-up Drive/Gmail media → populate VaultImage/VaultMed, next_undecided() (+43 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (48): Command, Gmail pipeline management command — bypasses HTTP auth entirely. Calls service f, action_reconcile(), action_restore_to_gmail(), action_trash(), gmail_discover(), gmail_download(), gmail_incremental() (+40 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (33): run_dry_run(), run_execute(), apply_protected_senders(), rules_run_all(), get_scheduler(), job_apply_protected_senders(), job_run_cleanup_rules(), APScheduler jobs for periodic Gmail sync and cleanup. All jobs are OFF by defaul (+25 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (40): export_audit_log(), export_messages(), gmail_empty_trash(), gmail_label(), gmail_profile(), gmail_push_webhook(), gmail_trash(), gmail_verify() (+32 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (21): ExifStripTest, _has_exif(), _make_minimal_jpeg(), make_staff(), MediaMetadataModelTest, Tests for media_vault — EXIF strip, MediaMetadata, video streaming, gallery., Calling strip_and_preserve twice on same path returns existing record., HEIC and other unsupported formats pass through unchanged. (+13 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (17): BaseCommand, Command, Permanently delete all messages currently in Gmail trash.  WARNING: This is irre, Command, _parse_eml(), Extract images and videos from downloaded .eml files into GmailAttachment record, Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples, Sanitise an untrusted attachment filename.     Handles: Windows backslash paths, (+9 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (13): DriveAssetAdmin, MediaItemAdmin, # IMPORTANT: Do NOT override admin.site.each_context here., RunLogAdmin, DriveAsset, MediaItem, Meta, One row per pipeline run.      totals schema:   {"discovered": int, "downloaded" (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (22): BulkMediaDecisionPayload, DriveDiscoverParams, DriveDownloadParams, ErrorDetail, ErrorResponse, GmailDiscoverParams, GmailSyncParams, LooseSchema (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.16
Nodes (18): CleanupAuditLogAdmin, CleanupRuleAdmin, GmailAttachmentAdmin, GmailMessageAdmin, GmailSyncStateAdmin, ProtectedSenderAdmin, RuleConditionInline, GmailFilterIn (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (24): GmailMessage, ProtectedSender, Emails from these senders are never trashed or deleted by any cleanup rule., IncrementalSyncTrashAddedTest, IncrementalSyncTrashRemovedTest, ProtectedSenderReconcileTest, PurgeExpiredTest, PurgeYoungRecordUntouchedTest (+16 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (22): Renew Gmail push notification watch — expires every 7 days., task_renew_gmail_watch(), _cleanup_partial(), download_file(), download_or_export_file(), download_photos_item(), _download_photos_item_legacy(), drive_service() (+14 more)

### Community 11 - "Community 11"
Cohesion: 0.2
Nodes (6): Command, Drive/Photos pipeline management command — bypasses HTTP auth entirely.  Usage:, sync_import(), copy_into_media(), deterministic_path(), sha256_file()

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (13): AssetOut, auth_connect(), export_assets(), FilterIn, list_assets(), Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, sync_commit_delete() (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (8): GmailLoopLogicTest, GmailProgressAPITest, make_message(), ProtectedSenderExclusionTest, Regression tests — each test is named after the bug it prevents.  Every test her, BUG: make gmail-loop called gmail_pipeline all on every iteration,     re-runnin, BUG: Ops console KPI labelled 'TRASHED' was actually showing prog.discovered, Regression: Protected senders must NEVER be affected by cleanup rules,     regar

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (5): Unit tests for google_media_backup — no DB, no network., TestDeterministicPath, TestGoogleExportMap, TestMimeClassification, TestSha256File

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (14): Record task failure on all GmailSyncState rows and fire Sentry if configured., Compare local VERIFIED messages against live Gmail — mark missing as SOFT_DELETE, Incremental Gmail sync — picks up new messages since last historyId., _record_task_failure(), task_gmail_incremental_sync(), task_gmail_reconcile(), Tests for Phase 2 — Gmail sync & reconciliation.  Covers: - Incremental sync: TR, test_404_marks_soft_deleted() (+6 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (3): GmailAttachmentTest, GmailMessageModelTest, GmailSyncStateTest

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (5): AdminTemplateDuplicateH1Test, CleanupRuleRatelimitTest, make_user(), BUG: Gmail dashboard template had its own <h1>Gmail Dashboard</h1>     on top of, BUG: Dry-run All Enabled Rules returned HTTP 500 because 'redis' Python     pack

### Community 18 - "Community 18"
Cohesion: 0.17
Nodes (4): make_message(), make_sync_state(), Create a GmailMessage with sensible defaults for reconciliation tests., Create a GmailSyncState with a valid history ID.

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (6): AccountsConfig, AppConfig, CoreConfig, GoogleGmailBackupConfig, GoogleMediaBackupConfig, MediaVaultConfig

### Community 20 - "Community 20"
Cohesion: 0.17
Nodes (11): Celery tasks for Drive/Photos pipeline. Scheduled via django_celery_beat — edita, Commit pending deletions — trash verified assets from Google., Discover new Google Photos items., Download a batch of DISCOVERED documents (exports Google native formats)., Import VERIFIED document DriveAssets into Wagtail VaultDocument., Download a batch of DISCOVERED photos., task_docs_download_batch(), task_docs_import_vault() (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.29
Nodes (4): MetadataSnapshot, Frozen snapshot of a GmailMessage at deletion time.      Stored in GmailMessage., Unit tests for google_gmail_backup.schemas — no DB, no network., TestMetadataSnapshot

### Community 22 - "Community 22"
Cohesion: 0.2
Nodes (9): Smoke tests — quick sanity checks that run in CI., Gmail Celery tasks can be imported without error., Media Celery tasks can be imported without error., All app models import without error., Django system check passes with no errors., test_celery_gmail_tasks_importable(), test_celery_media_tasks_importable(), test_django_check() (+1 more)

### Community 23 - "Community 23"
Cohesion: 0.25
Nodes (7): AbstractUser, BackupUserAdmin, Custom user admin — same as Django's default UserAdmin., BackupUser, Meta, Custom user model for BackDeezUp.      Always define a custom user model before, UserAdmin

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (8): code:bash (make migrate), code:bash (docker compose exec web python manage.py migrate accounts --), code:bash (docker compose exec web python manage.py shell -c "), Context, Custom User Model Migration Guide, For a fresh deployment (no existing data), For an existing deployment with users already in the DB, Verify

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (6): Action, Field, Logic, Meta, Operator, State

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): htmx_audit_log(), htmx_cleanup_status(), htmx_gmail_progress(), HTMX partial views for Gmail ops console. Returns HTML fragments for live update, Live cleanup job status — polled by HTMX every 3s when a job is running., Latest audit log entries — polled every 10s., Gmail pipeline progress bar fragment — includes disk usage stats.

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (5): LooseSchema, Project-wide Pydantic v2 schemas. Use these for input validation in ALL Django v, Base schema — ignores extra fields (safe for external API responses)., Base schema — forbids extra fields, strips whitespace from strings., StrictSchema

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (7): _mark_soft_deleted(), Celery tasks for Gmail pipeline and cleanup. These are the direct replacements f, Star + label messages from protected senders., Trigger a download batch — useful for on-demand pipeline from web UI., Mark a single GmailMessage as SOFT_DELETED with metadata snapshot., task_apply_protected_senders(), task_gmail_download_batch()

### Community 31 - "Community 31"
Cohesion: 0.29
Nodes (4): Build a validated MetadataSnapshot dict from a GmailMessage instance., snapshot_from_message(), Purge SOFT_DELETED records older than 90 days — set state to DELETED, keep .eml, task_purge_expired_soft_deletes()

### Community 32 - "Community 32"
Cohesion: 0.29
Nodes (7): sync_discover(), list_drive_files(), list_media_files(), Return one page of media files (images/videos) from Drive., Unified Drive file lister — media_only=True for images/videos, False for documen, Discover Drive documents (PDF, Office, Google native formats)., task_docs_discover()

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (3): EmptyTrashGuardTest, BUG: The ≥90% guard on empty-trash required ≥90% backup, but the missing     mes, dry_run with skip=true must not be blocked by backup % check.

### Community 35 - "Community 35"
Cohesion: 0.4
Nodes (3): ErrorResponseTest, BUG: except Exception: errors += len(chunk) with no logging.     User got delete, Response schema must always include last_error (even if null).

### Community 37 - "Community 37"
Cohesion: 0.4
Nodes (3): ConcurrentDownloaderTest, Feature: gmail_pipeline download now uses ThreadPoolExecutor.     Test that:, With no DISCOVERED messages, download exits without error.

## Knowledge Gaps
- **214 isolated node(s):** `Smoke tests — quick sanity checks that run in CI.`, `Django system check passes with no errors.`, `Gmail Celery tasks can be imported without error.`, `Media Celery tasks can be imported without error.`, `All app models import without error.` (+209 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Command` connect `Community 0` to `Community 8`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `VaultMedia` connect `Community 0` to `Community 4`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `GmailAttachment` connect `Community 8` to `Community 0`, `Community 2`, `Community 5`, `Community 16`, `Community 24`, `Community 26`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `GmailMessage` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailMessage` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `CleanupRule` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`CleanupRule` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `GmailSyncState` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailSyncState` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `ProtectedSender` (e.g. with `GmailSyncStateAdmin` and `GmailAttachmentAdmin`) actually correct?**
  _`ProtectedSender` has 34 INFERRED edges - model-reasoned connections that need verification._