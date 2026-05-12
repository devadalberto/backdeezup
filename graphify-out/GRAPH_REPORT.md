# Graph Report - backdeezup  (2026-05-12)

## Corpus Check
- 26 files · ~3,081 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 86 nodes · 104 edges · 24 communities (11 shown, 13 thin omitted)
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 15 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b8ed1fb1`
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

## God Nodes (most connected - your core abstractions)
1. `drive_service()` - 7 edges
2. `MediaItem` - 6 edges
3. `DriveAsset` - 6 edges
4. `RunLog` - 6 edges
5. `AssetOut` - 6 edges
6. `_save_creds()` - 5 edges
7. `photos_service()` - 5 edges
8. `FilterIn` - 5 edges
9. `_load_creds()` - 4 edges
10. `list_media_files()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `AssetOut` --uses--> `MediaItem`  [INFERRED]
  backend_django/google_media_backup/api.py → backend_django/google_media_backup/models.py
- `FilterIn` --uses--> `MediaItem`  [INFERRED]
  backend_django/google_media_backup/api.py → backend_django/google_media_backup/models.py
- `MediaItemAdmin` --uses--> `MediaItem`  [INFERRED]
  backend_django/google_media_backup/admin.py → backend_django/google_media_backup/models.py
- `RunLogAdmin` --uses--> `MediaItem`  [INFERRED]
  backend_django/google_media_backup/admin.py → backend_django/google_media_backup/models.py
- `DriveAssetAdmin` --uses--> `MediaItem`  [INFERRED]
  backend_django/google_media_backup/admin.py → backend_django/google_media_backup/models.py

## Communities (24 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.2
Nodes (16): sync_discover(), download_file(), drive_service(), list_common_files(), list_media_files(), list_photos_items(), _load_creds(), photos_service() (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (12): auth_connect(), list_assets(), Discover media items from Google Photos Library.     NOTE: These are NOT Drive f, Discover commonly-used document types in Drive (pdf, office, csv, archives, iWor, sync_commit_delete(), sync_discover_files(), sync_discover_photos(), sync_download() (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.28
Nodes (11): DriveAssetAdmin, each_context(), MediaItemAdmin, ops_link(), RunLogAdmin, AssetOut, FilterIn, DriveAsset (+3 more)

## Knowledge Gaps
- **18 isolated node(s):** `Run administrative tasks.`, `Return one page of media-like files (images/videos or shortcuts to them).     Lo`, `Google Photos Library API client.`, `Return mediaItems from Google Photos Library.     Note: these are NOT Drive file`, `Return one page of commonly-used document types in Drive.     Searches My Drive` (+13 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AssetOut` connect `Community 2` to `Community 1`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `FilterIn` connect `Community 2` to `Community 1`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `sync_discover_photos()` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `MediaItem` (e.g. with `AssetOut` and `FilterIn`) actually correct?**
  _`MediaItem` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `DriveAsset` (e.g. with `AssetOut` and `FilterIn`) actually correct?**
  _`DriveAsset` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `RunLog` (e.g. with `AssetOut` and `FilterIn`) actually correct?**
  _`RunLog` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `AssetOut` (e.g. with `DriveAsset` and `MediaItem`) actually correct?**
  _`AssetOut` has 3 INFERRED edges - model-reasoned connections that need verification._