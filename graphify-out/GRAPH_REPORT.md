# Graph Report - backdeezup  (2026-05-15)

## Corpus Check
- 60 files · ~23,500 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 614 nodes · 690 edges · 56 communities (44 shown, 12 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 51 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2eb78d44`
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

## God Nodes (most connected - your core abstractions)
1. `GmailSyncState` - 13 edges
2. `GmailMessage` - 13 edges
3. `gmail_service()` - 13 edges
4. `Changelog` - 13 edges
5. `GmailAPITest` - 12 edges
6. `DriveAPITest` - 11 edges
7. `Acknowledgements` - 11 edges
8. `GmailAttachment` - 10 edges
9. `GmailMessageModelTest` - 10 edges
10. `backdeezup` - 10 edges

## Surprising Connections (you probably didn't know these)
- `gmail_profile()` --calls--> `get_authenticated_email()`  [EXTRACTED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/services_gmail.py
- `action_trash_selected()` --calls--> `trash_message()`  [INFERRED]
  backend_django/google_gmail_backup/admin.py → backend_django/google_gmail_backup/services_gmail.py
- `gmail_service()` --calls--> `_load_creds()`  [INFERRED]
  backend_django/google_gmail_backup/services_gmail.py → backend_django/google_media_backup/services_google.py
- `gmail_service()` --calls--> `_save_creds()`  [INFERRED]
  backend_django/google_gmail_backup/services_gmail.py → backend_django/google_media_backup/services_google.py
- `GmailMessageOut` --uses--> `GmailMessage`  [INFERRED]
  backend_django/google_gmail_backup/api.py → backend_django/google_gmail_backup/models.py

## Communities (56 total, 12 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (35): auth_connect(), list_assets(), Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, sync_commit_delete(), sync_discover() (+27 more)

### Community 1 - "Community 1"
Cohesion: 0.1
Nodes (32): gmail_discover(), gmail_download(), gmail_incremental(), gmail_trash(), Incremental sync using historyId. Falls back to full discover on 404., Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWN, Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute., Full snapshot discovery — lists all message IDs and fetches metadata.     Stores (+24 more)

### Community 2 - "Community 2"
Cohesion: 0.1
Nodes (15): DriveAssetAdmin, each_context(), MediaItemAdmin, ops_link(), # IMPORTANT: Do NOT override admin.site.each_context here., RunLogAdmin, ops_console(), Minimal admin 'Operations Console' that calls your /api/* endpoints     with a s (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.4
Nodes (3): AppConfig, GoogleGmailBackupConfig, GoogleMediaBackupConfig

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (42): 1. Create `.env`, 2. Place Google OAuth credentials, 3. Build and start, 4. Run migrations, 5. Create superuser, 6. Authenticate with Google, 7. Verify the deployment, Acknowledgements (+34 more)

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
Nodes (24): action_trash_selected(), GmailAttachmentAdmin, GmailMessageAdmin, GmailSyncStateAdmin, gmail_label(), gmail_profile(), gmail_verify(), GmailFilterIn (+16 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (36): Admin Enhancements, API Enhancements, Architectural Philosophy, BackDeezUp, BackDeezUp Strengths, BackDeezUp Weaknesses, Blending Strategy: "Best of Both Worlds", code:python (class CleanupRule(models.Model):) (+28 more)

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (35): 1. Clone and configure, 2. Place Google credentials, 3. Build and start, 4. Initialise database and create superuser, 5. Authenticate with Google, code:bash (make discover HOST=http://192.168.88.60:8844), code:bash (make redeploy), code:bash (git pull origin main) (+27 more)

### Community 26 - "Community 26"
Cohesion: 0.22
Nodes (8): [0.1.0] - 2026-05-12, [0.5.1] - 2026-05-14, Added, Added, Changed, Changelog, Safety Features, [Unreleased]

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
Cohesion: 0.2
Nodes (10): [0.4.1] - 2026-05-13, [0.5.0] - 2026-05-14, Added, Added, Added, Added, Fixed, Fixed (+2 more)

### Community 49 - "Community 49"
Cohesion: 0.25
Nodes (8): [0.2.0] - 2026-05-13, Added, Added, Changed, Changed, Fixed, Fixed, Technical

### Community 50 - "Community 50"
Cohesion: 0.33
Nodes (7): [0.6.1] - 2026-05-15, [0.7.0] - 2026-05-15, Added, Added, Fixed, Fixed, Known Issues

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (6): [0.4.0] - 2026-05-13, Added, Changed, Changed, Fixed, Fixed

### Community 52 - "Community 52"
Cohesion: 0.4
Nodes (5): [0.3.0] - 2026-05-13, Added, Added, Changed, Changed

### Community 53 - "Community 53"
Cohesion: 0.4
Nodes (5): [0.4.2] - 2026-05-13, Added, Added, Changed, Changed

### Community 54 - "Community 54"
Cohesion: 0.67
Nodes (3): [0.6.0] - 2026-05-15, Added, Added

## Knowledge Gaps
- **280 isolated node(s):** `PreToolUse`, `BeforeTool`, `Run administrative tasks.`, `Full snapshot discovery — lists all message IDs and fetches metadata.     Stores`, `Incremental sync using historyId. Falls back to full discover on 404.` (+275 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **12 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `gmail_service()` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Why does `DriveAPITest` connect `Community 2` to `Community 18`?**
  _High betweenness centrality (0.008) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `GmailSyncState` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailSyncState` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `GmailMessage` (e.g. with `GmailMessageOut` and `GmailFilterIn`) actually correct?**
  _`GmailMessage` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `gmail_service()` (e.g. with `_load_creds()` and `_save_creds()`) actually correct?**
  _`gmail_service()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `GmailAPITest` (e.g. with `GmailMessage` and `GmailAttachment`) actually correct?**
  _`GmailAPITest` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `PreToolUse`, `BeforeTool`, `Run administrative tasks.` to the rest of the system?**
  _280 weakly-connected nodes found - possible documentation gaps or missing edges._