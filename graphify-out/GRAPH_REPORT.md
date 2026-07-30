# Graph Report - backdeezup  (2026-07-30)

## Corpus Check
- 128 files · ~64,360 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1726 nodes · 2838 edges · 143 communities (103 shown, 40 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 413 edges (avg confidence: 0.58)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `10eeba3c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- services_google.py
- apply_rule
- DriveAsset
- main
- AppConfig
- admin_ops_view
- google_gmail_backup/tasks.py
- Migration
- asgi.py
- wsgi.py
- DriveAPITest
- BackDeezUp — URL Index (PDX-CL1)
- Production deployment
- GmailProgressAPITest
- API Reference
- State reference
- BackDeezUp
- setup.md
- google_gmail_backup/admin.py
- run_all_enabled_rules
- 3. Build and start
- GOALS_DONE — backdeezup
- listing_controls.js
- dev.sh script
- Project Comparison: Gmail Cleanup vs BackDeezUp
- Deployment
- Changelog
- shared_context.md
- Authentication
- Installation
- Quick Start
- Architecture
- Handover & Architecture
- Contributing
- Acknowledgements
- Configuration
- [0.2.0] - 2026-05-13
- installed
- Data Model
- hooks
- hooks
- hooks
- 16. Git workflow
- 17. Sentry setup
- 21. End-of-session housekeeping prompt
- 9. Celery (background jobs)
- entrypoint.sh
- [0.4.1] - 2026-05-13
- VaultMedia
- [0.6.1] - 2026-05-15
- [0.2.0] - 2026-05-13
- [0.3.0] - 2026-05-13
- [0.4.0] - 2026-05-13
- autostart.sh
- google_token.json
- [0.1.0] - 2026-05-12
- 0002_alter_gmailmessage_from_address_and_more.py
- 0003_protectedsender_alter_gmailattachment_options_and_more.py
- gen-dev-certs.sh
- RuleCondition
- Media Vault CMS
- CleanupRule
- gmail_download
- google_gmail_backup/api.py
- urls.py
- post
- Operations Manual
- 0004_rulecondition.py
- 0002_mediagallerypage_photoreviewpage_vaulthomepage_and_more.py
- [0.4.2] - 2026-05-13
- CleanupAuditLog
- eml_path
- GmailMessageModelTest
- 0005_cleanupauditlog_affected_ids_truncated_and_more.py
- 0002_alter_driveasset_state_and_more.py
- ExifStripTest
- tests_unit.py
- BackDeezUp — Prompts & Playbook (2026-05-19)
- BackupUser
- [0.5.0] - 2026-05-14
- Custom User Model Migration Guide
- ProtectedSender
- backdeezup TODO
- OnclikAmpersandTest
- Command
- Migration
- google_media_backup/tasks.py
- backdeezup
- BaseCommand
- Quick start
- How it works
- BackDeezUp
- Operations manual
- gmail_service
- code:bash (make gen-certs)
- MetadataSnapshot
- celery_app.py
- task_gmail_reconcile
- GmailMessage
- google_media_backup/api.py
- scheduler.py
- GOALS_TODOS.md
- rule_builder_dry_run
- Project structure
- GmailAPITest
- 0007_soft_delete_reconciliation.py
- 4. Gmail backup pipeline
- 6. Gmail cleanup rules
- 12. TLS certificate management
- ai-dev/GOALS_TODOS.md
- 13. Autostart after VM reboot
- 14. Monitoring and diagnostics
- 7. Extract family media attachments
- graphify
- graphify
- graphify
- 0008_add_last_error_to_sync_state.py
- 0009_add_from_email_normalized.py
- 0010_add_token_path_to_sync_state.py
- 0003_add_sha256_to_vault_models.py
- 18. Add a second Google account
- 1. Start a new AI session
- 20. Model review prompt (reusable)
- 5. Empty Gmail trash

## God Nodes (most connected - your core abstractions)
1. `GmailMessage` - 64 edges
2. `CleanupRule` - 58 edges
3. `GmailSyncState` - 56 edges
4. `ProtectedSender` - 48 edges
5. `CleanupAuditLog` - 41 edges
6. `apply_rule()` - 41 edges
7. `RuleCondition` - 39 edges
8. `BackDeezUp` - 33 edges
9. `VaultMedia` - 30 edges
10. `gmail_service()` - 29 edges

## Surprising Connections (you probably didn't know these)
- `gmail_discover()` --references--> `post()`  [EXTRACTED]
  backend_django/google_gmail_backup/api.py → run_pipeline.py
- `gmail_incremental()` --calls--> `get()`  [EXTRACTED]
  backend_django/google_gmail_backup/api.py → run_pipeline.py
- `gmail_incremental()` --references--> `post()`  [EXTRACTED]
  backend_django/google_gmail_backup/api.py → run_pipeline.py
- `gmail_download()` --calls--> `get()`  [EXTRACTED]
  backend_django/google_gmail_backup/api.py → run_pipeline.py
- `gmail_download()` --references--> `post()`  [EXTRACTED]
  backend_django/google_gmail_backup/api.py → run_pipeline.py

## Import Cycles
- None detected.

## Communities (143 total, 40 thin omitted)

### Community 0 - "services_google.py"
Cohesion: 0.10
Nodes (29): Command, BaseCommand, Setup Gmail push notifications via Google Cloud Pub/Sub.  Usage:     docker comp, Drive/Photos pipeline management command — bypasses HTTP auth entirely.  Usage:, _cleanup_partial(), download_file(), download_or_export_file(), download_photos_item() (+21 more)

### Community 1 - "apply_rule"
Cohesion: 0.08
Nodes (20): apply_rule(), _get_or_create_label(), _is_protected(), _normalize_email(), _protected_emails(), Cleanup rules engine. All actions support dry_run=True (default) — nothing touch, Extract bare email from 'Name <email>' format., Extract bare email from 'Name <email>' format. (+12 more)

### Community 2 - "DriveAsset"
Cohesion: 0.12
Nodes (20): DriveAssetAdmin, each_context(), MediaItemAdmin, ops_link(), action, register, # IMPORTANT: Do NOT override admin.site.each_context here., RunLogAdmin (+12 more)

### Community 4 - "AppConfig"
Cohesion: 0.12
Nodes (11): AppConfig, AccountsConfig, AppConfig, CoreConfig, AppConfig, GoogleGmailBackupConfig, AppConfig, GoogleMediaBackupConfig (+3 more)

### Community 5 - "admin_ops_view"
Cohesion: 0.50
Nodes (3): admin_ops_view(), staff_member_required, ensure_csrf_cookie

### Community 6 - "google_gmail_backup/tasks.py"
Cohesion: 0.14
Nodes (16): shared_task, Celery tasks for Gmail pipeline and cleanup. These are the direct replacements f, Star + label messages from protected senders., Star + label messages from protected senders., Run all enabled cleanup rules., Run all enabled cleanup rules., Trigger a download batch — useful for on-demand pipeline from web UI., Star + label messages from protected senders. (+8 more)

### Community 7 - "Migration"
Cohesion: 0.25
Nodes (4): Migration, Migration, Migration, Migration

### Community 10 - "DriveAPITest"
Cohesion: 0.15
Nodes (3): DriveAPITest, DriveAssetModelTest, TestCase

### Community 11 - "BackDeezUp — URL Index (PDX-CL1)"
Cohesion: 0.20
Nodes (9): API Docs (Django Ninja interactive), BackDeezUp — URL Index (PDX-CL1), Drive / Photos API (`/api/`), External / Docs, Gmail API (`/api/gmail/`), HTMX fragments (internal, used by templates), Media Vault API (`/api/vault/`), OAuth (+1 more)

### Community 12 - "Production deployment"
Cohesion: 0.17
Nodes (16): 1. Create `.env`, 2. Place Google OAuth credentials, 5. Create superuser, 6 — Authenticate with Google, 7. Verify the deployment, Autostart on VM boot, Celery (background jobs), code:bash (make auth) (+8 more)

### Community 13 - "GmailProgressAPITest"
Cohesion: 0.22
Nodes (3): GmailProgressAPITest, make_message(), BUG: Ops console KPI labelled 'TRASHED' was actually showing prog.discovered

### Community 14 - "API Reference"
Cohesion: 0.10
Nodes (25): API (base: /api), API Reference, Asset listing, Authentication, code:bash (curl -k https://localhost:8445/api/docs), code:json ({), code:json ({), code:json ({) (+17 more)

### Community 15 - "State reference"
Cohesion: 0.13
Nodes (16): code:mermaid (stateDiagram-v2), code:block2 (MIN_RETENTION_DAYS=3  # default, configurable in .env), DELETE_PENDING, DELETED, Deletion modes, DISCOVERED, DOWNLOADED, Gmail Message States (+8 more)

### Community 16 - "BackDeezUp"
Cohesion: 0.12
Nodes (16): Architecture, BackDeezUp, Before you start, code:block1 (Your Google Account), code:mermaid (stateDiagram-v2), Documentation sections, FAQ, gmail_josevaldes_cleanup (+8 more)

### Community 18 - "google_gmail_backup/admin.py"
Cohesion: 0.09
Nodes (22): action_restore_to_gmail(), action_trash(), action_trash_selected(), CleanupAuditLogAdmin, CleanupRuleAdmin, GmailAttachmentAdmin, GmailMessageAdmin, GmailSyncStateAdmin (+14 more)

### Community 19 - "run_all_enabled_rules"
Cohesion: 0.25
Nodes (8): rules_run_all(), Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records., Run all enabled CleanupRules. Returns list of audit log records.      Uses a Red, run_all_enabled_rules(), ratelimit

### Community 20 - "3. Build and start"
Cohesion: 0.33
Nodes (6): 3. Build and start, CI/CD pipeline (GitHub Actions), code:bash (# Import Drive + Gmail media into Wagtail vault), code:mermaid (flowchart LR), Media vault, Ongoing operations

### Community 21 - "GOALS_DONE — backdeezup"
Cohesion: 0.33
Nodes (5): 2026-07-23 — Completed phases through Phase 15, 2026-07-23 — Recent documentation work, GOALS_DONE — backdeezup, Known completed blockers, Project current state

### Community 22 - "listing_controls.js"
Cohesion: 0.83
Nodes (3): buildDropdown(), getParam(), injectControls()

### Community 24 - "Project Comparison: Gmail Cleanup vs BackDeezUp"
Cohesion: 0.05
Nodes (36): Admin Enhancements, API Enhancements, Architectural Philosophy, BackDeezUp, BackDeezUp Strengths, BackDeezUp Weaknesses, Blending Strategy: "Best of Both Worlds", code:python (class CleanupRule(models.Model):) (+28 more)

### Community 25 - "Deployment"
Cohesion: 0.06
Nodes (35): 1. Clone and configure, 2. Place Google credentials, 3. Build and start, 4. Initialise database and create superuser, 5. Authenticate with Google, code:bash (make discover HOST=http://192.168.88.60:8844), code:bash (make redeploy), code:bash (git pull origin main) (+27 more)

### Community 26 - "Changelog"
Cohesion: 0.22
Nodes (8): [0.8.0] - 2026-05-15, [0.9.0] - 2026-05-16, Added, Added, Changelog, Default cleanup rules seeded (all disabled — review before enabling), Protected senders seeded, [Unreleased]

### Community 27 - "shared_context.md"
Cohesion: 0.05
Nodes (43): API endpoints (`/api`), Apps, Autostart on VM boot, CI/CD pipeline (GitHub Actions), code:bash (make preflight                        # ALWAYS run first), code:block2 (C:\Users\Administrator\repos\github\), code:block3 (WINWEB01 boots → Windows login), code:block4 (lint+test+sast-bandit+sast-safety (parallel, in containers)) (+35 more)

### Community 28 - "Authentication"
Cohesion: 0.11
Nodes (23): Authenticate (headless server — no browser on server), Authentication, code:bash (cp '/mnt/c/Users/Administrator/Downloads/client_secret_48605), code:bash (python3 -c "import json; d=json.load(open('secrets/google_cl), code:block3 (http://localhost:18444/), code:powershell ($wslIp = wsl -d Debian -- hostname -I | ForEach-Object { $_.), code:bash (make auth), code:block6 (Starting local OAuth server on port 18444...) (+15 more)

### Community 29 - "Installation"
Cohesion: 0.13
Nodes (19): Clone and sync, code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (curl -LsSf https://astral.sh/uv/install.sh | sh), code:powershell (powershell -ExecutionPolicy ByPass -c "irm https://astral.sh), code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (uv run python backend_django/manage.py --version), code:bash (mkdir -p secrets), Create OAuth credentials (+11 more)

### Community 30 - "Quick Start"
Cohesion: 0.10
Nodes (26): 1. Clone and configure, 1. Clone and install, 2. Configure environment, 2. Place Google credentials, 3. Generate TLS certificates, 3. Place Google credentials, 4. Migrate and start, 4. Pre-flight check (+18 more)

### Community 31 - "Architecture"
Cohesion: 0.13
Nodes (14): Architecture, code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), code:mermaid (sequenceDiagram), code:mermaid (erDiagram), code:mermaid (flowchart TD), Critical invariants, Data model (+6 more)

### Community 32 - "Handover & Architecture"
Cohesion: 0.13
Nodes (14): code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), code:mermaid (erDiagram), code:mermaid (sequenceDiagram), code:mermaid (flowchart TD), Critical invariants, Data model, Deployment topology (+6 more)

### Community 33 - "Contributing"
Cohesion: 0.13
Nodes (14): AI agent coordination, Code conventions, code:bash (git clone https://github.com/devadalberto/backdeezup.git), code:bash (# Start the dev server), code:bash (# 1. Update CHANGELOG.md — move [Unreleased] items to a new ), code:bash (graphify update .), Contributing, Development workflow (+6 more)

### Community 34 - "Acknowledgements"
Cohesion: 0.15
Nodes (12): Acknowledgements, AI collaboration, Code quality, code:block1 (MIT License), Core framework, Documentation, Google integration, Infrastructure (+4 more)

### Community 35 - "Configuration"
Cohesion: 0.18
Nodes (10): Admin UI labels, code:env (DJANGO_SECRET_KEY=change-me-to-a-long-random-string), Configuration, CORS / CSRF, Deletion behaviour, Django core, Google API, Required (+2 more)

### Community 36 - "[0.2.0] - 2026-05-13"
Cohesion: 0.29
Nodes (7): [0.1.0] - 2026-05-12, [0.2.0] - 2026-05-13, Added, Changed, Changelog, Fixed, [Unreleased]

### Community 37 - "installed"
Cohesion: 0.22
Nodes (8): installed, auth_provider_x509_cert_url, auth_uri, client_id, client_secret, project_id, redirect_uris, token_uri

### Community 38 - "Data Model"
Cohesion: 0.25
Nodes (7): code:mermaid (erDiagram), Data Model, DriveAsset, Entity relationship diagram, MediaItem, Notes, RunLog

### Community 48 - "[0.4.1] - 2026-05-13"
Cohesion: 0.22
Nodes (9): [0.4.1] - 2026-05-13, Added, Added, Added, Added, Fixed, Fixed, Fixed (+1 more)

### Community 49 - "VaultMedia"
Cohesion: 0.07
Nodes (55): AbstractDocument, AbstractImage, AbstractMedia, AbstractRendition, next_undecided(), Media Vault API — progress, decisions, import status, import trigger. Mounted at, Overview of vault contents and review progress., Returns the next undecided item for the review UI. (+47 more)

### Community 50 - "[0.6.1] - 2026-05-15"
Cohesion: 0.18
Nodes (13): [0.10.0] - 2026-05-16, [0.6.1] - 2026-05-15, [0.7.0] - 2026-05-15, Added, Added, Added, Added, Added (+5 more)

### Community 51 - "[0.2.0] - 2026-05-13"
Cohesion: 0.15
Nodes (13): [0.2.0] - 2026-05-13, Added, Added, Added, Added, Changed, Changed, Changed (+5 more)

### Community 52 - "[0.3.0] - 2026-05-13"
Cohesion: 0.20
Nodes (10): [0.3.0] - 2026-05-13, [0.5.1] - 2026-05-14, Added, Added, Added, Added, Changed, Changed (+2 more)

### Community 53 - "[0.4.0] - 2026-05-13"
Cohesion: 0.18
Nodes (11): [0.4.0] - 2026-05-13, Added, Added, Changed, Changed, Changed, Changed, Fixed (+3 more)

### Community 56 - "[0.1.0] - 2026-05-12"
Cohesion: 0.33
Nodes (6): [0.1.0] - 2026-05-12, Added, Added, Added, Added, Safety Features

### Community 61 - "RuleCondition"
Cohesion: 0.10
Nodes (26): A single condition in a compound rule query.     Multiple conditions are AND/OR-, A single condition inside a compound CleanupRule query.     Conditions are order, A single condition inside a compound CleanupRule query.     Conditions are order, RuleCondition, Record a keep/delete/undecided decision for a vault item., record_decision(), BulkMediaDecisionPayload, DriveDiscoverParams (+18 more)

### Community 62 - "Media Vault CMS"
Cohesion: 0.09
Nodes (21): Access, Adding new pages from the CMS, code:bash (docker compose exec web python manage.py createsuperuser), code:block2 (/vault/my-gallery/?keep=keep), code:python (from schemas import MediaDecisionPayload), Create the site and vault homepage, Documents, First-time setup (+13 more)

### Community 63 - "CleanupRule"
Cohesion: 0.17
Nodes (9): Seed inbox-specific cleanup rules based on observed inbox content. Safe to run m, Management command to seed protected senders and default cleanup rules. Safe to, Migration, Action, CleanupRule, Field, Logic, Meta (+1 more)

### Community 64 - "gmail_download"
Cohesion: 0.10
Nodes (26): gmail_discover(), gmail_download(), gmail_incremental(), Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN (+18 more)

### Community 66 - "google_gmail_backup/api.py"
Cohesion: 0.15
Nodes (20): export_audit_log(), export_messages(), get_audit_log(), gmail_empty_trash(), gmail_profile(), gmail_progress(), gmail_push_webhook(), list_messages() (+12 more)

### Community 67 - "urls.py"
Cohesion: 0.08
Nodes (37): oauth_callback(), htmx_stats(), landing_page(), require_GET, HTMX partial — returns live stats cards. Polled every 10s., gmail_dashboard(), gmail_ops(), gmail_rule_builder() (+29 more)

### Community 68 - "post"
Cohesion: 0.10
Nodes (22): gmail_label(), gmail_trash(), gmail_verify(), Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute. (+14 more)

### Community 69 - "Operations Manual"
Cohesion: 0.05
Nodes (43): Browse media, Celery, Check progress, code:bash (make gmail-discover), code:bash (make docs-progress), code:bash (make photos-delete LIMIT=100    # trash Photos from Google), code:bash (make import-media                    # all sources), code:bash (make up        # start all 6 containers) (+35 more)

### Community 75 - "[0.4.2] - 2026-05-13"
Cohesion: 0.15
Nodes (13): [0.4.2] - 2026-05-13, [0.6.0] - 2026-05-15, Added, Added, Added, Added, Added, Added (+5 more)

### Community 76 - "CleanupAuditLog"
Cohesion: 0.06
Nodes (27): CleanupAuditLog, Immutable log of every cleanup action (dry-run or real)., Immutable append-only log of every cleanup action (dry-run or real)., Immutable append-only log of every cleanup action (dry-run or real)., AdminTemplateDuplicateH1Test, CleanupRuleRatelimitTest, ConcurrentDownloaderTest, EmptyTrashGuardTest (+19 more)

### Community 77 - "eml_path"
Cohesion: 0.29
Nodes (7): eml_dir(), eml_path(), ensure_eml_path(), Returns deterministic .eml path: gmail/<account>/<year>/<month>/<gmail_id>.eml, Returns the directory path for .eml storage. Does NOT create the directory., Returns .eml path AND creates the directory. Use when writing files., Alias for ensure_eml_path — kept for backward compatibility.

### Community 78 - "GmailMessageModelTest"
Cohesion: 0.14
Nodes (4): GmailAttachmentTest, GmailMessageModelTest, GmailSyncStateTest, TestCase

### Community 82 - "ExifStripTest"
Cohesion: 0.06
Nodes (22): ExifStripTest, _has_exif(), _make_minimal_jpeg(), make_staff(), MediaMetadataModelTest, TestCase, Tests for media_vault — EXIF strip, MediaMetadata, video streaming, gallery., Calling strip_and_preserve twice on same path returns existing record. (+14 more)

### Community 83 - "tests_unit.py"
Cohesion: 0.14
Nodes (6): unit, Unit tests for google_media_backup — no DB, no network., TestDeterministicPath, TestGoogleExportMap, TestMimeClassification, TestSha256File

### Community 84 - "BackDeezUp — Prompts & Playbook (2026-05-19)"
Cohesion: 0.12
Nodes (15): 10. Re-authenticate with Google, 11. Unblock Google Photos, 15. Running tests, 19. Security audit prompt (reusable), 2. First deploy on a new machine, 8. Identity groups (family media tagging), BackDeezUp — Prompts & Playbook (2026-05-19), code:bash (# Delete stale token) (+7 more)

### Community 85 - "BackupUser"
Cohesion: 0.24
Nodes (9): AbstractUser, BackupUserAdmin, register, Custom user admin — same as Django's default UserAdmin., BackupUser, Meta, Custom user model for BackDeezUp.     Extends AbstractUser with no additional fi, Custom user model for BackDeezUp.      Always define a custom user model before (+1 more)

### Community 86 - "[0.5.0] - 2026-05-14"
Cohesion: 0.25
Nodes (8): [0.5.0] - 2026-05-14, Added, Added, Added, Added, Fixed, Fixed, Security

### Community 87 - "Custom User Model Migration Guide"
Cohesion: 0.22
Nodes (8): code:bash (make migrate), code:bash (docker compose exec web python manage.py migrate accounts --), code:bash (docker compose exec web python manage.py shell -c "), Context, Custom User Model Migration Guide, For a fresh deployment (no existing data), For an existing deployment with users already in the DB, Verify

### Community 88 - "ProtectedSender"
Cohesion: 0.09
Nodes (30): ProtectedSender, Emails from these senders are never trashed or deleted by any cleanup rule., Emails from these senders are never trashed or deleted by any cleanup rule., Emails from these senders are always kept — never trashed, never deleted., IncrementalSyncTrashAddedTest, IncrementalSyncTrashRemovedTest, make_message(), make_sync_state() (+22 more)

### Community 91 - "backdeezup TODO"
Cohesion: 0.06
Nodes (31): backdeezup TODO, Bugs fixed this session (2026-06-02), Docs a human needs to operate it, Fix incremental sync (task_gmail_incremental_sync), Full reconciliation task, Handoff checklist (Claude steps back), Known blockers, Live reconciliation results (first run) (+23 more)

### Community 99 - "google_media_backup/tasks.py"
Cohesion: 0.08
Nodes (30): list_common_files(), list_drive_files(), list_photos_items(), Return mediaItems from Google Photos Library.     Note: these are NOT Drive file, Return mediaItems from Google Photos Library., Return mediaItems from Google Photos Library., Return one page of commonly-used document types in Drive.     Searches My Drive, Return mediaItems from Google Photos Library. (+22 more)

### Community 108 - "BaseCommand"
Cohesion: 0.05
Nodes (28): Command, BaseCommand, Command, _parse_eml(), BaseCommand, Extract images and videos from downloaded .eml files into GmailAttachment record, Parse a .eml file and yield (attachment_id, filename, mime_type, data) tuples, Sanitise an untrusted attachment filename.     Handles: Windows backslash paths, (+20 more)

### Community 109 - "Quick start"
Cohesion: 0.13
Nodes (22): 1 — Clone and configure, 2 — Google OAuth credentials, 5 — Build and start, 7 — Seed rules and run initial setup, After first-time deploy — seed rules and apply protected senders, code:bash (make build && make up && make migrate && make superuser), code:bash (make seed-rules        # seed 15 cleanup rules with correct ), code:bash (git clone git@github-dev:devadalberto/backdeezup.git) (+14 more)

### Community 111 - "How it works"
Cohesion: 0.13
Nodes (19): code:bash (git clone git@github.com:devadalberto/backdeezup.git && cd b), code:block19 (WINWEB01 boots), code:block2 (nginx → gunicorn/Django → PostgreSQL), code:bash (make help              # full list), code:mermaid (flowchart TD), Data model, Drive / Photos, Drive / Photos pipeline (+11 more)

### Community 112 - "BackDeezUp"
Cohesion: 0.11
Nodes (18): 6-container Docker stack, Access, Acknowledgements, Admin UI, AI agent collaboration, API reference, Apps, Architecture (+10 more)

### Community 113 - "Operations manual"
Cohesion: 0.33
Nodes (7): 4. Run migrations, code:bash (# Full discovery (finds all message IDs)), code:bash (make redeploy         # git pull + rebuild + restart + migra), Empty Gmail trash, Gmail backup, Maintenance, Operations manual

### Community 115 - "gmail_service"
Cohesion: 0.11
Nodes (23): action_reconcile(), apply_protected_senders(), batch_modify_labels(), batch_trash_messages(), delete_message_permanent(), get_attachment_data(), get_message_full(), get_message_raw() (+15 more)

### Community 116 - "code:bash (make gen-certs)"
Cohesion: 0.50
Nodes (4): 3 — TLS certificates (localhost/dev), code:bash (make gen-certs), Enable automatic scheduling (3x per day), Key make targets

### Community 118 - "MetadataSnapshot"
Cohesion: 0.08
Nodes (19): LooseSchema, MetadataSnapshot, BaseModel, field_validator, Project-wide Pydantic v2 schemas. Use these for input validation in ALL Django v, Base schema — ignores extra fields (safe for external API responses)., Base schema — forbids extra fields, strips whitespace from strings., Frozen snapshot of a GmailMessage at deletion time.      Stored in GmailMessage. (+11 more)

### Community 121 - "task_gmail_reconcile"
Cohesion: 0.08
Nodes (27): mock_drive_service(), mock_gmail_service(), mock_photos_service(), sample_drive_asset(), sample_gmail_message(), Record task failure on all GmailSyncState rows and fire Sentry if configured., Compare local VERIFIED messages against live Gmail — mark missing as…, Incremental Gmail sync — picks up new messages since last historyId. (+19 more)

### Community 123 - "GmailMessage"
Cohesion: 0.15
Nodes (14): GmailFilterIn, GmailMessageOut, Schema, SyncResult, HTMX partial views for Gmail ops console. Returns HTML fragments for live update, Permanently delete all messages currently in Gmail trash.  WARNING: This is irre, GmailMessage, GmailSyncState (+6 more)

### Community 124 - "google_media_backup/api.py"
Cohesion: 0.15
Nodes (17): auth_connect(), sync_discover(), sync_download(), sync_import(), list_media_files(), Return one page of media files (images/videos) from Drive., Return one page of media files (images/videos) from Drive., Return one page of media files (images/videos) from Drive. (+9 more)

### Community 126 - "scheduler.py"
Cohesion: 0.19
Nodes (14): get_scheduler(), job_apply_protected_senders(), job_gmail_incremental_sync(), job_run_cleanup_rules(), APScheduler jobs for periodic Gmail sync and cleanup. All jobs are OFF by defaul, Incremental Gmail sync — picks up new messages since last historyId., Star + label messages from protected senders., Run all enabled cleanup rules (dry_run=False). (+6 more)

### Community 128 - "GOALS_TODOS.md"
Cohesion: 0.50
Nodes (3): Full phase commands for GOALS.md dispatcher. Read-only reference., GOALS_TODOS.md -- backdeezup operations runbook, Live phase tracking is in TODO.md -- update checkboxes there, not here.

### Community 130 - "rule_builder_dry_run"
Cohesion: 0.17
Nodes (13): POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}     Retu, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}     Retu, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}     Retu, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30, "name":, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30, "name":, POST body: {         "name": "LinkedIn jobs", "description": "...",         "act, POST body: {         "name": "LinkedIn jobs", "description": "...",         "act, POST body: {         "name": "LinkedIn jobs", "description": "...",         "act (+5 more)

### Community 131 - "Project structure"
Cohesion: 0.29
Nodes (7): 4 — Pre-flight check, code:block23 (# Setup), code:block24 (backdeezup/), code:bash (make preflight), Make targets reference, Project structure, Subsequent runs (incremental)

### Community 135 - "4. Gmail backup pipeline"
Cohesion: 0.29
Nodes (7): 4. Gmail backup pipeline, code:bash (# Step 1 — discover all message IDs), code:block5 (Show me the current Gmail backup progress. Query the DB and ), code:bash (# Check what's in each state), Initial full backup, Monitor progress, When download stalls (DISCOVERED = 0 but progress stuck)

### Community 136 - "6. Gmail cleanup rules"
Cohesion: 0.29
Nodes (7): 6. Gmail cleanup rules, Add a new rule (prompt), code:bash (make seed-rules          # 15 core rules (5d/15d thresholds)), code:block9 (Add a new cleanup rule to seed_inbox_rules.py that:), Current rule thresholds, Execute rules, Seed / update rules

### Community 139 - "12. TLS certificate management"
Cohesion: 0.33
Nodes (6): 12. TLS certificate management, code:bash (make gen-certs), code:powershell (certutil -addstore -f "ROOT" "C:\Users\Administrator\repos\g), Generate (first time or renewal), Trust on Firefox, Trust on Windows (run PowerShell as Administrator)

### Community 144 - "ai-dev/GOALS_TODOS.md"
Cohesion: 0.50
Nodes (3): Full phase commands for GOALS.md dispatcher. Read-only reference., GOALS_TODOS.md -- backdeezup operations runbook, Live phase tracking is in TODO.md -- update checkboxes there, not here.

### Community 145 - "13. Autostart after VM reboot"
Cohesion: 0.40
Nodes (5): 13. Autostart after VM reboot, 3. Standard upgrade (after merging a PR), code:block16 (Windows boots → login → Startup folder bat runs), code:bash (# On Debian), code:bash (# Debian service)

### Community 146 - "14. Monitoring and diagnostics"
Cohesion: 0.50
Nodes (4): 14. Monitoring and diagnostics, code:bash (make logs              # all container logs), code:bash (docker compose exec web python manage.py shell --verbosity 0), Useful shell queries

### Community 147 - "7. Extract family media attachments"
Cohesion: 0.50
Nodes (4): 7. Extract family media attachments, code:bash (# Count what would be extracted (safe — no files written)), code:bash (make import-media ARGS="--source drive"), Import Drive media to vault

## Knowledge Gaps
- **408 isolated node(s):** `Migration`, `Migration`, `Migration`, `Migration`, `Migration` (+403 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **40 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GmailMessage` connect `GmailMessage` to `gmail_download`, `apply_rule`, `google_gmail_backup/api.py`, `urls.py`, `GmailAPITest`, `google_gmail_backup/tasks.py`, `BaseCommand`, `CleanupAuditLog`, `GmailMessageModelTest`, `GmailProgressAPITest`, `google_gmail_backup/admin.py`, `OnclikAmpersandTest`, `ProtectedSender`, `task_gmail_reconcile`, `scheduler.py`, `CleanupRule`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `VaultMedia` connect `VaultMedia` to `GmailMessage`, `ExifStripTest`, `urls.py`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `GmailSyncState` connect `GmailMessage` to `gmail_download`, `apply_rule`, `google_gmail_backup/api.py`, `urls.py`, `GmailAPITest`, `google_gmail_backup/tasks.py`, `BaseCommand`, `CleanupAuditLog`, `GmailMessageModelTest`, `GmailProgressAPITest`, `google_gmail_backup/admin.py`, `ProtectedSender`, `OnclikAmpersandTest`, `scheduler.py`, `CleanupRule`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `GmailMessage` (e.g. with `CleanupAuditLogAdmin` and `CleanupRuleAdmin`) actually correct?**
  _`GmailMessage` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 40 inferred relationships involving `CleanupRule` (e.g. with `CleanupAuditLogAdmin` and `CleanupRuleAdmin`) actually correct?**
  _`CleanupRule` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `GmailSyncState` (e.g. with `CleanupAuditLogAdmin` and `CleanupRuleAdmin`) actually correct?**
  _`GmailSyncState` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 34 inferred relationships involving `ProtectedSender` (e.g. with `CleanupAuditLogAdmin` and `CleanupRuleAdmin`) actually correct?**
  _`ProtectedSender` has 34 INFERRED edges - model-reasoned connections that need verification._