# Graph Report - backdeezup  (2026-05-19)

## Corpus Check
- 115 files · ~55,229 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1302 nodes · 1793 edges · 126 communities (101 shown, 25 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 314 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `3a9c50ac`
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
- [[_COMMUNITY_Community 101|Community 101]]
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
- [[_COMMUNITY_Community 121|Community 121]]
- [[_COMMUNITY_Community 122|Community 122]]
- [[_COMMUNITY_Community 123|Community 123]]
- [[_COMMUNITY_Community 124|Community 124]]

## God Nodes (most connected - your core abstractions)
1. `GmailMessage` - 35 edges
2. `GmailSyncState` - 34 edges
3. `CleanupRule` - 33 edges
4. `ProtectedSender` - 29 edges
5. `RuleCondition` - 29 edges
6. `CleanupAuditLog` - 28 edges
7. `apply_rule()` - 28 edges
8. `BackDeezUp` - 27 edges
9. `VaultMedia` - 21 edges
10. `gmail_service()` - 19 edges

## Surprising Connections (you probably didn't know these)
- `rule_dry_run()` --calls--> `apply_rule()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py
- `rule_execute()` --calls--> `apply_rule()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py
- `rules_run_all()` --calls--> `run_all_enabled_rules()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py
- `export_audit_log()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/exports.py
- `export_messages()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/exports.py

## Communities (126 total, 25 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (52): Command, Drive/Photos pipeline management command — bypasses HTTP auth entirely.  Usage:, gmail_service(), auth_connect(), export_assets(), list_assets(), Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover media items from Google Photos Library.     NOTE: These are NOT Drive f (+44 more)

### Community 1 - "Community 1"
Cohesion: 0.16
Nodes (9): run_dry_run(), run_execute(), apply_rule(), Apply a CleanupRule. Returns a CleanupAuditLog record.     Protected senders are, Apply a CleanupRule. Returns a CleanupAuditLog record.     Protected senders are, AuditLogTest, Protected sender must not appear in dry-run affected_gmail_ids., Regression: Every real rule execution must create a CleanupAuditLog entry.     D (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (19): DriveAssetAdmin, each_context(), MediaItemAdmin, ops_link(), # IMPORTANT: Do NOT override admin.site.each_context here., RunLogAdmin, ops_console(), Minimal admin 'Operations Console' that calls your /api/* endpoints     with a s (+11 more)

### Community 4 - "Community 4"
Cohesion: 0.1
Nodes (14): AccountsConfig, AppConfig, CoreConfig, GoogleGmailBackupConfig, get_scheduler(), job_apply_protected_senders(), job_run_cleanup_rules(), APScheduler jobs for periodic Gmail sync and cleanup. All jobs are OFF by defaul (+6 more)

### Community 12 - "Community 12"
Cohesion: 0.17
Nodes (13): 2. Place Google OAuth credentials, 6 — Authenticate with Google, 7. Verify the deployment, Autostart on VM boot, Celery (background jobs), code:bash (make auth), code:bash (# Re-seed rules (idempotent — safe to run anytime, updates t), code:bash (make celery-logs      # tail worker + beat logs) (+5 more)

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
Nodes (16): CleanupAuditLogAdmin, CleanupRuleAdmin, GmailAttachmentAdmin, GmailMessageAdmin, GmailSyncStateAdmin, ProtectedSenderAdmin, RuleConditionInline, CleanupAuditLog (+8 more)

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
Cohesion: 0.05
Nodes (44): API endpoints (`/api`), Apps, Autostart on VM boot, CI/CD pipeline (GitHub Actions), code:bash (make preflight                        # ALWAYS run first), code:block2 (C:\Users\Administrator\repos\github\), code:block3 (WINWEB01 boots → Windows login), code:block4 (lint+test+sast-bandit+sast-safety (parallel, in containers)) (+36 more)

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
Cohesion: 0.14
Nodes (21): BulkMediaDecisionPayload, DriveDiscoverParams, DriveDownloadParams, ErrorDetail, ErrorResponse, GmailDiscoverParams, GmailSyncParams, LooseSchema (+13 more)

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (21): Access, Adding new pages from the CMS, code:bash (docker compose exec web python manage.py createsuperuser), code:block2 (/vault/my-gallery/?keep=keep), code:python (from schemas import MediaDecisionPayload), Create the site and vault homepage, Documents, First-time setup (+13 more)

### Community 63 - "Community 63"
Cohesion: 0.22
Nodes (10): GmailFilterIn, GmailMessageOut, SyncResult, CleanupRule, GmailMessage, One row per Gmail message discovered and/or downloaded., GmailLoopLogicTest, BUG: make gmail-loop called gmail_pipeline all on every iteration,     re-runnin (+2 more)

### Community 64 - "Community 64"
Cohesion: 0.18
Nodes (13): gmail_discover(), gmail_incremental(), Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Fast discovery — stores only message IDs (no per-message API calls).     Metadat, Fast discovery — stores only message IDs (no per-message API calls).     Metadat, extract_headers() (+5 more)

### Community 65 - "Community 65"
Cohesion: 0.18
Nodes (11): apply_protected_senders(), gmail_label(), batch_modify_labels(), modify_labels(), Apply label changes to multiple messages in one API call — O(1) instead of O(n)., Apply label changes to multiple messages in one API call — O(1) instead of O(n)., apply_protected_sender_rules(), Special rule: star + label + keep in inbox messages from protected senders. (+3 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (10): export_audit_log(), export_messages(), gmail_empty_trash(), Return field/operator/logic choices for the frontend builder., Return field/operator/logic choices for the frontend builder., Permanently delete all messages in Gmail trash.     dry_run=true (default): coun, rule_builder_fields(), rule_dry_run() (+2 more)

### Community 67 - "Community 67"
Cohesion: 0.42
Nodes (9): _coerce(), _export_csv(), _export_json(), _export_pdf(), export_queryset(), _export_xlsx(), _export_xml(), Export engine — CSV, XLSX, JSON, XML, PDF. Usage: call export_queryset(request, (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.22
Nodes (9): action_trash(), action_trash_selected(), gmail_trash(), Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Move a single message to Gmail trash. Logs errors instead of silently returning, Move a single message to Gmail trash. Logs errors instead of silently returning (+1 more)

### Community 69 - "Community 69"
Cohesion: 0.18
Nodes (9): Command, Seed v2 smart cleanup rules for LinkedIn, job boards, recruiters, and marketing, compile_conditions(), conditions_to_dict(), Query compiler: translates RuleCondition rows into a Gmail q= search string.  Gm, Serialize conditions for the frontend builder., Convert a single condition to a Gmail query term. Returns None if not applicable, Takes a queryset/list of RuleCondition ordered by `order`.     Returns a Gmail q (+1 more)

### Community 70 - "Community 70"
Cohesion: 0.22
Nodes (10): gmail_profile(), job_gmail_incremental_sync(), Incremental Gmail sync — picks up new messages since last historyId., get_authenticated_email(), list_history(), Returns (history_records, new_history_id) or raises Exception on 404.     Caller, Returns (history_records, new_history_id) or raises Exception on 404.     Caller, Returns (history_records, new_history_id) or raises Exception on 404.     Caller (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.15
Nodes (13): [0.4.2] - 2026-05-13, [0.6.0] - 2026-05-15, Added, Added, Added, Added, Added, Added (+5 more)

### Community 76 - "Community 76"
Cohesion: 0.11
Nodes (9): AdminTemplateDuplicateH1Test, CleanupRuleRatelimitTest, make_message(), make_user(), Regression tests — each test is named after the bug it prevents.  Every test her, BUG: Gmail dashboard template had its own <h1>Gmail Dashboard</h1>     on top of, BUG: Gmail dashboard template had its own <h1>Gmail Dashboard</h1>     on top of, BUG: Dry-run All Enabled Rules returned HTTP 500 because 'redis' Python     pack (+1 more)

### Community 77 - "Community 77"
Cohesion: 0.14
Nodes (14): batch_trash_messages(), eml_dir(), eml_path(), ensure_eml_path(), get_attachment_data(), Trash multiple messages using Gmail batchModify. Returns count of successful tra, Trash multiple messages using Gmail batchModify. Returns count of successful tra, Returns deterministic .eml path: gmail/<account>/<year>/<month>/<gmail_id>.eml (+6 more)

### Community 78 - "Community 78"
Cohesion: 0.12
Nodes (7): GmailAttachmentTest, GmailMessageModelTest, GmailSyncStateTest, ProtectedSenderExclusionTest, Regression: Protected senders must NEVER be affected by cleanup rules,     regar, Regression: Protected senders must NEVER be affected by cleanup rules,     regar, TestCase

### Community 82 - "Community 82"
Cohesion: 0.06
Nodes (21): ExifStripTest, _has_exif(), _make_minimal_jpeg(), make_staff(), MediaMetadataModelTest, Tests for media_vault — EXIF strip, MediaMetadata, video streaming, gallery., Calling strip_and_preserve twice on same path returns existing record., HEIC and other unsupported formats pass through unchanged. (+13 more)

### Community 83 - "Community 83"
Cohesion: 0.17
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
Cohesion: 0.33
Nodes (3): GmailProgressAPITest, BUG: Ops console KPI labelled 'TRASHED' was actually showing prog.discovered, BUG: Ops console KPI labelled 'TRASHED' was actually showing prog.discovered

### Community 89 - "Community 89"
Cohesion: 0.25
Nodes (7): htmx_audit_log(), htmx_cleanup_status(), htmx_gmail_progress(), HTMX partial views for Gmail ops console. Returns HTML fragments for live update, Live cleanup job status — polled by HTMX every 3s when a job is running., Latest audit log entries — polled every 10s., Gmail pipeline progress bar fragment — includes disk usage stats.

### Community 91 - "Community 91"
Cohesion: 0.4
Nodes (4): GmailSyncState, One row per synced Gmail account — tracks historyId for incremental sync., One row per synced account — tracks historyId for incremental sync., One row per synced account — tracks historyId for incremental sync.

### Community 94 - "Community 94"
Cohesion: 0.39
Nodes (3): OnclikAmpersandTest, BUG: onclick="call('url?a=1&b=2')" — the & is parsed as &amp; by the     browser, BUG: onclick="call('url?a=1&b=2')" — the & is parsed as &amp; by the     browser

### Community 95 - "Community 95"
Cohesion: 0.17
Nodes (5): CleanupRulesEngineTest, Tests for services_rules.py — the core cleanup engine., Tests for services_rules.py — the core cleanup engine., Rule with min_age_days=7 should include recent message but exclude nothing old., Rule with min_age_days=7 should include recent message but exclude nothing old.

### Community 96 - "Community 96"
Cohesion: 0.25
Nodes (5): EmptyTrashGuardTest, BUG: The ≥90% guard on empty-trash required ≥90% backup, but the missing     mes, BUG: The ≥90% guard on empty-trash required ≥90% backup, but the missing     mes, dry_run with skip=true must not be blocked by backup % check., dry_run with skip=true must not be blocked by backup % check.

### Community 98 - "Community 98"
Cohesion: 0.29
Nodes (5): ErrorResponseTest, BUG: except Exception: errors += len(chunk) with no logging.     User got delete, BUG: except Exception: errors += len(chunk) with no logging.     User got delete, Response schema must always include last_error (even if null)., Response schema must always include last_error (even if null).

### Community 99 - "Community 99"
Cohesion: 0.2
Nodes (9): _get_or_create_label(), _is_protected(), _normalize_email(), _protected_emails(), Cleanup rules engine. All actions support dry_run=True (default) — nothing touch, Extract bare email from 'Name <email>' format., Extract bare email from 'Name <email>' format., Get Gmail label ID by name, creating it if needed. (+1 more)

### Community 101 - "Community 101"
Cohesion: 0.18
Nodes (11): POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}     Retu, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}     Retu, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30, "name":, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30, "name":, POST body: {         "name": "LinkedIn jobs", "description": "...",         "act, POST body: {         "name": "LinkedIn jobs", "description": "...",         "act, rule_builder_dry_run(), rule_builder_preview() (+3 more)

### Community 102 - "Community 102"
Cohesion: 0.22
Nodes (9): gmail_download(), Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, get_message_metadata(), Fetch metadata-only (no body) — cheap, 20 quota units., Fetch metadata-only (no body) — cheap, 20 quota units., Fetch metadata-only (no body) — cheap, 20 quota units. (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.07
Nodes (15): BaseCommand, Command, Permanently delete all messages currently in Gmail trash.  WARNING: This is irre, Command, _parse_eml(), Extract images and videos from downloaded .eml files into GmailAttachment record, Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples, Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples (+7 more)

### Community 109 - "Community 109"
Cohesion: 0.16
Nodes (18): 1 — Clone and configure, 2 — Google OAuth credentials, 5 — Build and start, 7 — Seed rules and run initial setup, code:bash (make build && make up && make migrate && make superuser), code:bash (make seed-rules        # seed 15 cleanup rules with correct ), code:bash (git clone git@github-dev:devadalberto/backdeezup.git), code:bash (# Generate Django secret key) (+10 more)

### Community 110 - "Community 110"
Cohesion: 0.18
Nodes (8): ConcurrentDownloaderTest, Feature: gmail_pipeline download now uses ThreadPoolExecutor.     Test that:, Feature: gmail_pipeline download now uses ThreadPoolExecutor.     Test that:, With no DISCOVERED messages, download exits without error., With no DISCOVERED messages, download exits without error., BUG: shared_context claimed Gmail was complete at 10010/10010 but actual     DB, BUG: shared_context claimed Gmail was complete at 10010/10010 but actual     DB, SyncStateTotalTest

### Community 111 - "Community 111"
Cohesion: 0.14
Nodes (18): 6-container Docker stack, Architecture, code:mermaid (flowchart LR), code:block19 (WINWEB01 boots), code:mermaid (stateDiagram-v2), code:mermaid (stateDiagram-v2), code:mermaid (flowchart TD), Data model (+10 more)

### Community 112 - "Community 112"
Cohesion: 0.12
Nodes (17): Access, Acknowledgements, Admin UI, AI agent collaboration, API reference, Apps, BackDeezUp, code:block23 (# Setup) (+9 more)

### Community 113 - "Community 113"
Cohesion: 0.15
Nodes (18): 1. Create `.env`, 3. Build and start, 4. Run migrations, 5. Create superuser, CI/CD pipeline (GitHub Actions), code:bash (# Full discovery (finds all message IDs)), code:bash (make discover           # discover Drive media (images/video), code:bash (# Import Drive + Gmail media into Wagtail vault) (+10 more)

### Community 115 - "Community 115"
Cohesion: 0.29
Nodes (7): get_message_full(), get_message_raw(), Fetch full message including body., Fetch full message including body., Fetch full message including body., Fetch raw RFC822 bytes (.eml format)., Fetch raw RFC822 bytes (.eml format).

### Community 116 - "Community 116"
Cohesion: 0.2
Nodes (10): 3 — TLS certificates (localhost/dev), 4 — Pre-flight check, After first-time deploy — seed rules and apply protected senders, code:bash (make gen-certs), code:bash (make preflight), Enable automatic scheduling (3x per day), First-time deployment, Key make targets (+2 more)

### Community 117 - "Community 117"
Cohesion: 0.29
Nodes (7): Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records., run_all_enabled_rules(), Run all enabled cleanup rules., task_run_cleanup_rules()

### Community 118 - "Community 118"
Cohesion: 0.33
Nodes (5): Celery tasks for Gmail pipeline and cleanup. These are the direct replacements f, Star + label messages from protected senders., Trigger a download batch — useful for on-demand pipeline from web UI., task_apply_protected_senders(), task_gmail_download_batch()

### Community 121 - "Community 121"
Cohesion: 0.33
Nodes (3): GmailPipelineCommandTest, BUG: gmail_pipeline discover had no --q flag.     make gmail-discover --q "in:tr, BUG: gmail_pipeline discover had no --q flag.     make gmail-discover --q "in:tr

### Community 122 - "Community 122"
Cohesion: 0.5
Nodes (4): gmail_verify(), Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages.

### Community 123 - "Community 123"
Cohesion: 0.5
Nodes (4): delete_message_permanent(), Requires https://mail.google.com/ scope., Permanently delete a message. Requires https://mail.google.com/ scope., Permanently delete a message. Requires https://mail.google.com/ scope.

### Community 124 - "Community 124"
Cohesion: 0.5
Nodes (4): list_message_ids(), Returns (list of {id, threadId}, nextPageToken).     q_filter supports Gmail sea, Returns (list of {id, threadId}, nextPageToken).     q_filter supports Gmail sea, Returns (list of {id, threadId}, nextPageToken).     q_filter supports Gmail sea

## Knowledge Gaps
- **546 isolated node(s):** `PreToolUse`, `BeforeTool`, `Project-wide Pydantic v2 schemas. Use these for input validation in ALL Django v`, `Base schema — forbids extra fields, strips whitespace from strings.`, `Base schema — ignores extra fields (safe for external API responses).` (+541 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **25 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GmailMessage` connect `Community 63` to `Community 96`, `Community 1`, `Community 98`, `Community 64`, `Community 76`, `Community 108`, `Community 78`, `Community 110`, `Community 18`, `Community 83`, `Community 84`, `Community 88`, `Community 121`, `Community 90`, `Community 94`, `Community 95`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `Command` connect `Community 49` to `Community 2`, `Community 18`, `Community 108`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Why does `gmail_service()` connect `Community 0` to `Community 65`, `Community 66`, `Community 1`, `Community 68`, `Community 102`, `Community 70`, `Community 108`, `Community 77`, `Community 115`, `Community 123`, `Community 124`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `GmailMessage` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailMessage` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `GmailSyncState` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailSyncState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `CleanupRule` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`CleanupRule` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `ProtectedSender` (e.g. with `GmailSyncStateAdmin` and `GmailAttachmentAdmin`) actually correct?**
  _`ProtectedSender` has 25 INFERRED edges - model-reasoned connections that need verification._