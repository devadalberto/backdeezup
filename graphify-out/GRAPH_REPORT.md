# Graph Report - backdeezup  (2026-05-16)

## Corpus Check
- 81 files · ~36,997 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 878 nodes · 1127 edges · 75 communities (59 shown, 16 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 164 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `8fc19aad`
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

## God Nodes (most connected - your core abstractions)
1. `GmailSyncState` - 18 edges
2. `GmailMessage` - 18 edges
3. `Changelog` - 16 edges
4. `gmail_service()` - 15 edges
5. `GmailAttachment` - 14 edges
6. `[0.2.0] - 2026-05-13` - 14 edges
7. `CleanupRule` - 13 edges
8. `RuleCondition` - 13 edges
9. `CleanupAuditLog` - 13 edges
10. `apply_rule()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `export_audit_log()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/exports.py
- `export_messages()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/exports.py
- `export_assets()` --calls--> `export_queryset()`  [INFERRED]
  backend_django/google_media_backup/api.py → backend_django/google_gmail_backup/exports.py
- `rule_dry_run()` --calls--> `apply_rule()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py
- `rule_execute()` --calls--> `apply_rule()`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_rules.py

## Communities (75 total, 16 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (36): auth_connect(), export_assets(), list_assets(), Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, sync_commit_delete() (+28 more)

### Community 1 - "Community 1"
Cohesion: 0.14
Nodes (17): run_dry_run(), run_execute(), rule_dry_run(), rule_execute(), rules_run_all(), apply_rule(), _get_or_create_label(), _is_protected() (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (15): DriveAssetAdmin, each_context(), MediaItemAdmin, ops_link(), # IMPORTANT: Do NOT override admin.site.each_context here., RunLogAdmin, ops_console(), Minimal admin 'Operations Console' that calls your /api/* endpoints     with a s (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (12): AppConfig, GoogleGmailBackupConfig, get_scheduler(), job_apply_protected_senders(), job_run_cleanup_rules(), APScheduler jobs for periodic Gmail sync and cleanup. All jobs are OFF by defaul, Star + label messages from protected senders., Run all enabled cleanup rules (dry_run=False). (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (53): 1. Create `.env`, 2. Place Google OAuth credentials, 3. Build and start, 4. Run migrations, 5. Create superuser, 6. Authenticate with Google, 7. Verify the deployment, Acknowledgements (+45 more)

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
Cohesion: 0.06
Nodes (34): BaseCommand, Command, Management command to seed protected senders and default cleanup rules. Safe to, CleanupAuditLogAdmin, CleanupRuleAdmin, GmailAttachmentAdmin, GmailMessageAdmin, GmailSyncStateAdmin (+26 more)

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
Cohesion: 0.07
Nodes (26): API endpoints (`/api`), code:mermaid (flowchart LR), code:mermaid (stateDiagram-v2), code:mermaid (erDiagram), code:mermaid (sequenceDiagram), code:block5 (DriveAsset ──FK──> MediaItem), code:block6 (DISCOVERED -> DOWNLOADED -> IMPORTED -> VERIFIED -> DELETE_P), Conventions for AI agents (+18 more)

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
Cohesion: 0.09
Nodes (39): AbstractDocument, AbstractImage, AbstractMedia, AbstractRendition, MediaDecision, Meta, Custom Wagtail image model.     Links back to source (Drive asset or Gmail attac, Custom document model for PDFs and other non-media files. (+31 more)

### Community 50 - "Community 50"
Cohesion: 0.18
Nodes (13): [0.10.0] - 2026-05-16, [0.6.1] - 2026-05-15, [0.7.0] - 2026-05-15, Added, Added, Added, Added, Added (+5 more)

### Community 51 - "Community 51"
Cohesion: 0.05
Nodes (38): [0.2.0] - 2026-05-13, [0.4.0] - 2026-05-13, [0.4.2] - 2026-05-13, [0.6.0] - 2026-05-15, Added, Added, Added, Added (+30 more)

### Community 52 - "Community 52"
Cohesion: 0.22
Nodes (9): [0.3.0] - 2026-05-13, Added, Added, Added, Added, Changed, Changed, Changed (+1 more)

### Community 53 - "Community 53"
Cohesion: 0.22
Nodes (9): [0.5.0] - 2026-05-14, Added, Added, Added, Added, Fixed, Fixed, Fixed (+1 more)

### Community 54 - "Community 54"
Cohesion: 0.73
Nodes (5): get(), main(), post(), run_drive(), run_gmail()

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (6): [0.1.0] - 2026-05-12, Added, Added, Added, Added, Safety Features

### Community 61 - "Community 61"
Cohesion: 0.15
Nodes (18): BulkMediaDecisionPayload, DriveDiscoverParams, DriveDownloadParams, ErrorDetail, ErrorResponse, GmailDiscoverParams, GmailSyncParams, LooseSchema (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (21): Access, Adding new pages from the CMS, code:bash (docker compose exec web python manage.py createsuperuser), code:block2 (/vault/my-gallery/?keep=keep), code:python (from schemas import MediaDecisionPayload), Create the site and vault homepage, Documents, First-time setup (+13 more)

### Community 63 - "Community 63"
Cohesion: 0.14
Nodes (15): POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}     Retu, POST body: {"conditions": [...], "action": "trash", "min_age_days": 30, "name":, POST body: {         "name": "LinkedIn jobs", "description": "...",         "act, rule_builder_dry_run(), rule_builder_preview(), rule_builder_save(), compile_conditions(), conditions_to_dict() (+7 more)

### Community 64 - "Community 64"
Cohesion: 0.19
Nodes (15): gmail_discover(), gmail_download(), gmail_incremental(), Incremental sync using historyId. Falls back to full discover on 404., Incremental sync using historyId. Falls back to full discover on 404., Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Fast discovery — stores only message IDs (no per-message API calls).     Metadat (+7 more)

### Community 65 - "Community 65"
Cohesion: 0.2
Nodes (12): delete_message_permanent(), eml_path(), get_attachment_data(), get_message_full(), get_message_raw(), gmail_service(), list_message_ids(), Requires https://mail.google.com/ scope. (+4 more)

### Community 66 - "Community 66"
Cohesion: 0.17
Nodes (7): export_audit_log(), export_messages(), gmail_verify(), Verify .eml file exists on disk for DOWNLOADED messages., Verify .eml file exists on disk for DOWNLOADED messages., Return field/operator/logic choices for the frontend builder., rule_builder_fields()

### Community 67 - "Community 67"
Cohesion: 0.42
Nodes (9): _coerce(), _export_csv(), _export_json(), _export_pdf(), export_queryset(), _export_xlsx(), _export_xml(), Export engine — CSV, XLSX, JSON, XML, PDF. Usage: call export_queryset(request, (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.33
Nodes (6): action_trash(), action_trash_selected(), gmail_trash(), Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., trash_message()

### Community 69 - "Community 69"
Cohesion: 0.33
Nodes (6): apply_protected_senders(), gmail_label(), modify_labels(), apply_protected_sender_rules(), Special rule: star + label + keep in inbox messages from protected senders., Special rule: star + label + keep in inbox messages from protected senders.

### Community 70 - "Community 70"
Cohesion: 0.33
Nodes (6): gmail_profile(), job_gmail_incremental_sync(), Incremental Gmail sync — picks up new messages since last historyId., get_authenticated_email(), list_history(), Returns (history_records, new_history_id) or raises Exception on 404.     Caller

## Knowledge Gaps
- **378 isolated node(s):** `PreToolUse`, `BeforeTool`, `Project-wide Pydantic v2 schemas. Use these for input validation in ALL Django v`, `Base schema — forbids extra fields, strips whitespace from strings.`, `Base schema — ignores extra fields (safe for external API responses).` (+373 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **16 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `gmail_service()` connect `Community 65` to `Community 64`, `Community 1`, `Community 0`, `Community 68`, `Community 69`, `Community 70`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `GmailMessage` connect `Community 18` to `Community 64`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Why does `Changelog` connect `Community 26` to `Community 48`, `Community 50`, `Community 51`, `Community 52`, `Community 53`, `Community 56`?**
  _High betweenness centrality (0.010) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `GmailSyncState` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailSyncState` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `GmailMessage` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailMessage` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `gmail_service()` (e.g. with `_load_creds()` and `_save_creds()`) actually correct?**
  _`gmail_service()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `GmailAttachment` (e.g. with `GmailSyncStateAdmin` and `GmailAttachmentAdmin`) actually correct?**
  _`GmailAttachment` has 11 INFERRED edges - model-reasoned connections that need verification._