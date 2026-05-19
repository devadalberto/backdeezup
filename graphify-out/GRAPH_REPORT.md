# Graph Report - backdeezup  (2026-05-19)

## Corpus Check
- 114 files · ~53,154 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1268 nodes · 1732 edges · 121 communities (95 shown, 26 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 314 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `dda8c06b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
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
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]
- [[_COMMUNITY_Community 110|Community 110]]
- [[_COMMUNITY_Community 111|Community 111]]
- [[_COMMUNITY_Community 112|Community 112]]
- [[_COMMUNITY_Community 113|Community 113]]
- [[_COMMUNITY_Community 114|Community 114]]
- [[_COMMUNITY_Community 115|Community 115]]
- [[_COMMUNITY_Community 116|Community 116]]
- [[_COMMUNITY_Community 117|Community 117]]
- [[_COMMUNITY_Community 118|Community 118]]
- [[_COMMUNITY_Community 119|Community 119]]

## God Nodes (most connected - your core abstractions)
1. `GmailMessage` - 35 edges
2. `GmailSyncState` - 34 edges
3. `CleanupRule` - 33 edges
4. `ProtectedSender` - 29 edges
5. `RuleCondition` - 29 edges
6. `CleanupAuditLog` - 28 edges
7. `apply_rule()` - 28 edges
8. `VaultMedia` - 21 edges
9. `gmail_service()` - 19 edges
10. `GmailAttachment` - 18 edges

## Surprising Connections (you probably didn't know these)
- `rule_dry_run()` --calls--> `apply_rule()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py
- `rule_execute()` --calls--> `apply_rule()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py
- `export_audit_log()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/exports.py
- `export_messages()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/exports.py
- `export_assets()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_media_backup/api.py → backend_django/google_gmail_backup/exports.py

## Communities (121 total, 26 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.16
Nodes (17): auth_connect(), download_file(), drive_service(), _load_creds(), photos_service(), Google Photos Library API client., Google Photos Library API client., Google Photos Library API client. (+9 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (36): run_dry_run(), run_execute(), rules_run_all(), apply_rule(), _get_or_create_label(), _is_protected(), _normalize_email(), _protected_emails() (+28 more)

### Community 2 - "Community 2"
Cohesion: 0.13
Nodes (13): DriveAssetAdmin, each_context(), MediaItemAdmin, ops_link(), # IMPORTANT: Do NOT override admin.site.each_context here., RunLogAdmin, DriveAsset, MediaItem (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (14): AccountsConfig, AppConfig, CoreConfig, GoogleGmailBackupConfig, get_scheduler(), job_apply_protected_senders(), job_run_cleanup_rules(), APScheduler jobs for periodic Gmail sync and cleanup. All jobs are OFF by defaul (+6 more)

### Community 12 - "Community 12"
Cohesion: 0.2
Nodes (12): 2. Place Google OAuth credentials, 3. Build and start, 6. Authenticate with Google, 7. Verify the deployment, code:bash (python -c "import secrets; print(secrets.token_urlsafe(50))"), code:bash (mkdir -p secrets), code:bash (# Build image (runs collectstatic automatically)), code:bash (# Open the Swagger UI in a browser and call POST /auth/conne) (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (25): API (base: /api), API Reference, Asset listing, Authentication, code:json ({), code:json ({), code:json ({), code:json ({) (+17 more)

### Community 15 - "Community 15"
Cohesion: 0.13
Nodes (14): code:mermaid (stateDiagram-v2), code:block2 (MIN_RETENTION_DAYS=3  # default, configurable in .env), DELETE_PENDING, DELETED, Deletion modes, DISCOVERED, DOWNLOADED, IMPORTED (+6 more)

### Community 16 - "Community 16"
Cohesion: 0.2
Nodes (9): Architecture, BackDeezUp, code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), gmail_josevaldes_cleanup, Key features, Pipeline, Quick navigation (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.14
Nodes (20): CleanupAuditLogAdmin, CleanupRuleAdmin, GmailAttachmentAdmin, GmailMessageAdmin, GmailSyncStateAdmin, ProtectedSenderAdmin, RuleConditionInline, GmailFilterIn (+12 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (36): Admin Enhancements, API Enhancements, Architectural Philosophy, BackDeezUp, BackDeezUp Strengths, BackDeezUp Weaknesses, Blending Strategy: "Best of Both Worlds", code:python (class CleanupRule(models.Model):) (+28 more)

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (35): 1. Clone and configure, 2. Place Google credentials, 3. Build and start, 4. Initialise database and create superuser, 5. Authenticate with Google, code:bash (make discover HOST=http://192.168.88.60:8844), code:bash (make redeploy), code:bash (git pull origin main) (+27 more)

### Community 26 - "Community 26"
Cohesion: 0.18
Nodes (10): [0.5.1] - 2026-05-14, [0.8.0] - 2026-05-15, [0.9.0] - 2026-05-16, Added, Added, Changed, Changelog, Default cleanup rules seeded (all disabled — review before enabling) (+2 more)

### Community 27 - "Community 27"
Cohesion: 0.06
Nodes (38): API endpoints (`/api`), Apps, code:bash (make preflight              # ALWAYS run first — checks Dock), code:bash (# Personal repos), code:block3 (C:\Users\Administrator\repos\github\), code:bash (make redeploy), code:block5 (DriveAsset ──FK──> MediaItem), code:block6 (DISCOVERED -> DOWNLOADED -> IMPORTED -> VERIFIED -> DELETE_P) (+30 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (23): Authenticate (headless server — no browser on server), Authentication, code:bash (cp '/mnt/c/Users/Administrator/Downloads/client_secret_48605), code:bash (python3 -c "import json; d=json.load(open('secrets/google_cl), code:block3 (http://localhost:18444/), code:powershell ($wslIp = wsl -d Debian -- hostname -I | ForEach-Object { $_.), code:bash (make auth), code:block6 (Starting local OAuth server on port 18444...) (+15 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (18): Clone and sync, code:bash (curl -LsSf https://astral.sh/uv/install.sh | sh), code:powershell (powershell -ExecutionPolicy ByPass -c "irm https://astral.sh), code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (uv run python backend_django/manage.py --version), code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (mkdir -p secrets) (+10 more)

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (18): 1. Clone and install, 2. Configure environment, 3. Place Google credentials, 4. Migrate and start, 5. Authenticate with Google, 6. Run the pipeline, 7. Browse the admin, code:bash (git clone https://github.com/devadalberto/backdeezup.git) (+10 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (14): Architecture, code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), code:mermaid (sequenceDiagram), code:mermaid (erDiagram), code:mermaid (flowchart TD), Critical invariants, Data model (+6 more)

### Community 32 - "Community 32"
Cohesion: 0.13
Nodes (14): code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), code:mermaid (erDiagram), code:mermaid (sequenceDiagram), code:mermaid (flowchart TD), Critical invariants, Data model, Deployment topology (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (13): AI agent coordination, Code conventions, code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (# Start the dev server), code:bash (# 1. Update CHANGELOG.md — move [Unreleased] items to a new ), code:bash (graphify update .), Contributing, Development workflow (+5 more)

### Community 34 - "Community 34"
Cohesion: 0.15
Nodes (12): Acknowledgements, AI collaboration, Code quality, code:block1 (MIT License), Core framework, Documentation, Google integration, Infrastructure (+4 more)

### Community 35 - "Community 35"
Cohesion: 0.18
Nodes (10): Admin UI labels, code:env (DJANGO_SECRET_KEY=change-me-to-a-long-random-string), Configuration, CORS / CSRF, Deletion behaviour, Django core, Google API, Required (+2 more)

### Community 36 - "Community 36"
Cohesion: 0.22
Nodes (8): [0.1.0] - 2026-05-12, [0.2.0] - 2026-05-13, Added, Added, Changed, Changelog, Fixed, [Unreleased]

### Community 37 - "Community 37"
Cohesion: 0.22
Nodes (8): installed, auth_provider_x509_cert_url, auth_uri, client_id, client_secret, project_id, redirect_uris, token_uri

### Community 38 - "Community 38"
Cohesion: 0.25
Nodes (7): code:mermaid (erDiagram), Data Model, DriveAsset, Entity relationship diagram, MediaItem, Notes, RunLog

### Community 48 - "Community 48"
Cohesion: 0.22
Nodes (9): [0.4.1] - 2026-05-13, Added, Added, Added, Added, Fixed, Fixed, Fixed (+1 more)

### Community 49 - "Community 49"
Cohesion: 0.06
Nodes (51): AbstractDocument, AbstractImage, AbstractMedia, AbstractRendition, Command, _guess_mime(), Import pipeline: scan backed-up Drive/Gmail media → populate VaultImage/VaultMed, next_undecided() (+43 more)

### Community 50 - "Community 50"
Cohesion: 0.18
Nodes (13): [0.10.0] - 2026-05-16, [0.6.1] - 2026-05-15, [0.7.0] - 2026-05-15, Added, Added, Added, Added, Added (+5 more)

### Community 51 - "Community 51"
Cohesion: 0.15
Nodes (13): [0.2.0] - 2026-05-13, Added, Added, Added, Added, Changed, Changed, Changed (+5 more)

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (9): [0.3.0] - 2026-05-13, Added, Added, Added, Added, Changed, Changed, Changed (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.17
Nodes (12): [0.4.0] - 2026-05-13, Added, Added, Added, Changed, Changed, Changed, Changed (+4 more)

### Community 54 - "Community 54"
Cohesion: 0.73
Nodes (5): get(), main(), post(), run_drive(), run_gmail()

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (6): [0.1.0] - 2026-05-12, Added, Added, Added, Added, Safety Features

### Community 61 - "Community 61"
Cohesion: 0.06
Nodes (41): BulkMediaDecisionPayload, DriveDiscoverParams, DriveDownloadParams, ErrorDetail, ErrorResponse, GmailDiscoverParams, GmailSyncParams, LooseSchema (+33 more)

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (21): Access, Adding new pages from the CMS, code:bash (docker compose exec web python manage.py createsuperuser), code:block2 (/vault/my-gallery/?keep=keep), code:python (from schemas import MediaDecisionPayload), Create the site and vault homepage, Documents, First-time setup (+13 more)

### Community 63 - "Community 63"
Cohesion: 0.2
Nodes (7): Command, Drive/Photos pipeline management command — bypasses HTTP auth entirely.  Usage:, sync_download(), sync_import(), copy_into_media(), deterministic_path(), sha256_file()

### Community 64 - "Community 64"
Cohesion: 0.13
Nodes (22): gmail_discover(), gmail_download(), gmail_incremental(), Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN (+14 more)

### Community 65 - "Community 65"
Cohesion: 0.12
Nodes (20): apply_protected_senders(), gmail_label(), batch_modify_labels(), batch_trash_messages(), delete_message_permanent(), get_attachment_data(), gmail_service(), modify_labels() (+12 more)

### Community 66 - "Community 66"
Cohesion: 0.11
Nodes (13): export_audit_log(), export_messages(), gmail_empty_trash(), gmail_verify(), Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages., Return field/operator/logic choices for the frontend builder. (+5 more)

### Community 67 - "Community 67"
Cohesion: 0.42
Nodes (9): _coerce(), _export_csv(), _export_json(), _export_pdf(), export_queryset(), _export_xlsx(), _export_xml(), Export engine — CSV, XLSX, JSON, XML, PDF. Usage: call export_queryset(request, (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.22
Nodes (9): action_trash(), action_trash_selected(), gmail_trash(), Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Move a single message to Gmail trash. Logs errors instead of silently returning, Move a single message to Gmail trash. Logs errors instead of silently returning (+1 more)

### Community 70 - "Community 70"
Cohesion: 0.22
Nodes (10): gmail_profile(), job_gmail_incremental_sync(), Incremental Gmail sync — picks up new messages since last historyId., get_authenticated_email(), list_history(), Returns (history_records, new_history_id) or raises Exception on 404.     Caller, Returns (history_records, new_history_id) or raises Exception on 404.     Caller, Returns (history_records, new_history_id) or raises Exception on 404.     Caller (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.15
Nodes (13): [0.4.2] - 2026-05-13, [0.6.0] - 2026-05-15, Added, Added, Added, Added, Added, Added (+5 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (7): AdminTemplateDuplicateH1Test, CleanupRuleRatelimitTest, make_user(), BUG: Gmail dashboard template had its own <h1>Gmail Dashboard</h1>     on top of, BUG: Gmail dashboard template had its own <h1>Gmail Dashboard</h1>     on top of, BUG: Dry-run All Enabled Rules returned HTTP 500 because 'redis' Python     pack, BUG: Dry-run All Enabled Rules returned HTTP 500 because 'redis' Python     pack

### Community 77 - "Community 77"
Cohesion: 0.2
Nodes (10): eml_dir(), eml_path(), ensure_eml_path(), Returns deterministic .eml path: gmail/<account>/<year>/<month>/<gmail_id>.eml, Returns the directory path for .eml storage. Does NOT create the directory., Returns the directory path for .eml storage. Does NOT create the directory., Returns .eml path AND creates the directory. Use when writing files., Returns .eml path AND creates the directory. Use when writing files. (+2 more)

### Community 78 - "Community 78"
Cohesion: 0.12
Nodes (6): ProtectedSender, Emails from these senders are never trashed or deleted by any cleanup rule., Emails from these senders are always kept — never trashed, never deleted., GmailAttachmentTest, GmailMessageModelTest, GmailSyncStateTest

### Community 82 - "Community 82"
Cohesion: 0.06
Nodes (21): ExifStripTest, _has_exif(), _make_minimal_jpeg(), make_staff(), MediaMetadataModelTest, Tests for media_vault — EXIF strip, MediaMetadata, video streaming, gallery., Calling strip_and_preserve twice on same path returns existing record., HEIC and other unsupported formats pass through unchanged. (+13 more)

### Community 83 - "Community 83"
Cohesion: 0.25
Nodes (6): Action, Field, Logic, Meta, Operator, State

### Community 84 - "Community 84"
Cohesion: 0.18
Nodes (3): GmailAPITest, API endpoints must return 401 for unauthenticated requests., API endpoints must return 401 for unauthenticated requests.

### Community 85 - "Community 85"
Cohesion: 0.22
Nodes (8): AbstractUser, BackupUserAdmin, Custom user admin — same as Django's default UserAdmin., BackupUser, Meta, Custom user model for BackDeezUp.     Extends AbstractUser with no additional fi, Custom user model for BackDeezUp.      Always define a custom user model before, UserAdmin

### Community 86 - "Community 86"
Cohesion: 0.22
Nodes (9): [0.5.0] - 2026-05-14, Added, Added, Added, Added, Fixed, Fixed, Fixed (+1 more)

### Community 87 - "Community 87"
Cohesion: 0.22
Nodes (8): code:bash (make migrate), code:bash (docker compose exec web python manage.py migrate accounts --), code:bash (docker compose exec web python manage.py shell -c "), Context, Custom User Model Migration Guide, For a fresh deployment (no existing data), For an existing deployment with users already in the DB, Verify

### Community 88 - "Community 88"
Cohesion: 0.09
Nodes (15): GmailLoopLogicTest, GmailPipelineCommandTest, GmailProgressAPITest, make_message(), ProtectedSenderExclusionTest, Regression tests — each test is named after the bug it prevents.  Every test her, BUG: gmail_pipeline discover had no --q flag.     make gmail-discover --q "in:tr, BUG: make gmail-loop called gmail_pipeline all on every iteration,     re-runnin (+7 more)

### Community 89 - "Community 89"
Cohesion: 0.25
Nodes (7): htmx_audit_log(), htmx_cleanup_status(), htmx_gmail_progress(), HTMX partial views for Gmail ops console. Returns HTML fragments for live update, Live cleanup job status — polled by HTMX every 3s when a job is running., Latest audit log entries — polled every 10s., Gmail pipeline progress bar fragment — includes disk usage stats.

### Community 90 - "Community 90"
Cohesion: 0.22
Nodes (6): Command, Gmail pipeline management command — bypasses HTTP auth entirely. Calls service f, list_message_ids(), Returns (list of {id, threadId}, nextPageToken).     q_filter supports Gmail sea, Returns (list of {id, threadId}, nextPageToken).     q_filter supports Gmail sea, Returns (list of {id, threadId}, nextPageToken).     q_filter supports Gmail sea

### Community 91 - "Community 91"
Cohesion: 0.2
Nodes (6): Command, Permanently delete all messages currently in Gmail trash.  WARNING: This is irre, GmailSyncState, One row per synced Gmail account — tracks historyId for incremental sync., One row per synced account — tracks historyId for incremental sync., One row per synced account — tracks historyId for incremental sync.

### Community 94 - "Community 94"
Cohesion: 0.39
Nodes (3): OnclikAmpersandTest, BUG: onclick="call('url?a=1&b=2')" — the & is parsed as &amp; by the     browser, BUG: onclick="call('url?a=1&b=2')" — the & is parsed as &amp; by the     browser

### Community 95 - "Community 95"
Cohesion: 0.25
Nodes (5): AssetOut, export_assets(), FilterIn, list_assets(), sync_commit_delete()

### Community 96 - "Community 96"
Cohesion: 0.25
Nodes (5): EmptyTrashGuardTest, BUG: The ≥90% guard on empty-trash required ≥90% backup, but the missing     mes, BUG: The ≥90% guard on empty-trash required ≥90% backup, but the missing     mes, dry_run with skip=true must not be blocked by backup % check., dry_run with skip=true must not be blocked by backup % check.

### Community 98 - "Community 98"
Cohesion: 0.29
Nodes (5): ErrorResponseTest, BUG: except Exception: errors += len(chunk) with no logging.     User got delete, BUG: except Exception: errors += len(chunk) with no logging.     User got delete, Response schema must always include last_error (even if null)., Response schema must always include last_error (even if null).

### Community 99 - "Community 99"
Cohesion: 0.22
Nodes (9): Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, sync_discover_photos(), list_photos_items(), Return mediaItems from Google Photos Library.     Note: these are NOT Drive file, Return mediaItems from Google Photos Library., Return mediaItems from Google Photos Library. (+1 more)

### Community 102 - "Community 102"
Cohesion: 0.22
Nodes (9): Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, sync_discover_files(), list_common_files(), Return one page of commonly-used document types in Drive.     Searches My Drive, Return one page of document-type files from Drive., Return one page of document-type files from Drive. (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.09
Nodes (13): BaseCommand, Command, _parse_eml(), Extract images and videos from downloaded .eml files into GmailAttachment record, Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples, Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples, Sanitise an untrusted attachment filename.     Handles: Windows backslash paths,, Strip path traversal and dangerous chars from attachment filename. (+5 more)

### Community 109 - "Community 109"
Cohesion: 0.15
Nodes (17): After first-time deploy — seed rules and apply protected senders, code:bash (# Bash (Linux / Mac / WSL)), code:bash (make build && make up   # postgres + nginx on :8844), code:bash (# 1. Clone), code:bash (# Gmail — full discovery + download loop), code:bash (# .env), Deploy, Development commands (+9 more)

### Community 110 - "Community 110"
Cohesion: 0.18
Nodes (8): ConcurrentDownloaderTest, Feature: gmail_pipeline download now uses ThreadPoolExecutor.     Test that:, Feature: gmail_pipeline download now uses ThreadPoolExecutor.     Test that:, With no DISCOVERED messages, download exits without error., With no DISCOVERED messages, download exits without error., BUG: shared_context claimed Gmail was complete at 10010/10010 but actual     DB, BUG: shared_context claimed Gmail was complete at 10010/10010 but actual     DB, SyncStateTotalTest

### Community 111 - "Community 111"
Cohesion: 0.21
Nodes (12): code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), code:mermaid (stateDiagram-v2), code:mermaid (flowchart TD), Data model, Drive / Photos pipeline, Gmail cleanup rules, Gmail pipeline (+4 more)

### Community 112 - "Community 112"
Cohesion: 0.18
Nodes (10): Acknowledgements, Admin UI, AI agent collaboration, API reference, Apps, BackDeezUp, Configuration, Modern tooling (+2 more)

### Community 113 - "Community 113"
Cohesion: 0.17
Nodes (13): 1. Create `.env`, 4. Run migrations, 5. Create superuser, code:bash (make test-full          # ruff lint + 59 unit + regression t), code:env (# ── Django ────────────────────────────────────────────────), code:bash (python3 -c "import base64, os; print(base64.urlsafe_b64encod), code:bash (docker compose exec web python manage.py migrate), code:bash (docker compose exec web python manage.py createsuperuser) (+5 more)

### Community 115 - "Community 115"
Cohesion: 0.29
Nodes (7): get_message_full(), get_message_raw(), Fetch full message including body., Fetch full message including body., Fetch full message including body., Fetch raw RFC822 bytes (.eml format)., Fetch raw RFC822 bytes (.eml format).

### Community 116 - "Community 116"
Cohesion: 0.67
Nodes (3): code:block8 (make preflight          Check Docker, .env, google_client.js), Enable automatic scheduling (3x per day), Key make targets

### Community 117 - "Community 117"
Cohesion: 0.33
Nodes (6): sync_discover(), list_media_files(), Return one page of media files (images/videos) from Drive., Return one page of media files (images/videos) from Drive., Return one page of media files (images/videos) from Drive., Return one page of media-like files (images/videos or shortcuts to them).     Lo

## Knowledge Gaps
- **543 isolated node(s):** `PreToolUse`, `BeforeTool`, `Project-wide Pydantic v2 schemas. Use these for input validation in ALL Django v`, `Base schema — forbids extra fields, strips whitespace from strings.`, `Base schema — ignores extra fields (safe for external API responses).` (+538 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **26 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `gmail_service()` connect `Community 65` to `Community 64`, `Community 1`, `Community 66`, `Community 0`, `Community 68`, `Community 70`, `Community 115`, `Community 90`, `Community 91`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Why does `GmailMessage` connect `Community 18` to `Community 96`, `Community 1`, `Community 98`, `Community 64`, `Community 76`, `Community 108`, `Community 110`, `Community 78`, `Community 83`, `Community 84`, `Community 88`, `Community 90`, `Community 91`, `Community 94`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `Command` connect `Community 49` to `Community 2`, `Community 18`, `Community 108`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `GmailMessage` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailMessage` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `GmailSyncState` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailSyncState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `CleanupRule` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`CleanupRule` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `ProtectedSender` (e.g. with `GmailSyncStateAdmin` and `GmailAttachmentAdmin`) actually correct?**
  _`ProtectedSender` has 25 INFERRED edges - model-reasoned connections that need verification._