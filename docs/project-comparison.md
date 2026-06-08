# Project Comparison: Gmail Cleanup vs BackDeezUp

## Executive Summary

**Gmail Cleanup Project** ("old"): Admin-first Gmail backup, reporting, and safe cleanup platform  
**BackDeezUp** (current): API-first Google Photos/Drive backup with state-machine deletion guards

Both projects share core DNA: Google OAuth → ingest → backup → safe deletion with audit trails. The key difference is **scope** (Gmail vs Drive/Photos) and **UI philosophy** (admin-first vs API-first).

---

## Feature Matrix

| Feature | Gmail Cleanup | BackDeezUp | Winner |
|---------|---------------|------------|--------|
| **Core Domain** | Gmail messages/attachments | Drive files & Photos media | Different domains |
| **OAuth Strategy** | Multi-account, user-based | Single/multi account implied | Gmail ✓ (explicit multi) |
| **Scope Management** | Explicit per-account tracking | Not explicitly tracked | Gmail ✓ |
| **Primary UI** | Django Admin (dashboard-first) | Django Ninja API (API-first) | **Tie** (different use cases) |
| **API Layer** | Django Ninja + Swagger | Django Ninja + Swagger | Tie |
| **Data Model** | Messages, Attachments, Accounts, Rules | MediaItem, DriveAsset, RunLog | Both good |
| **State Machine** | Implicit (status fields) | Explicit 6-stage pipeline | BackDeezUp ✓ |
| **Safety Guards** | Dry-run, 2-step confirm, min 360d age | 2-proof deletion (file+DB), MIN_RETENTION_DAYS | **Tie** (both excellent) |
| **Deletion Modes** | Trash / Permanent with scope check | Trash / Hard with retention | Tie |
| **Audit Logs** | Immutable, append-only, detailed | RunLog with status tracking | Gmail ✓ (more detailed) |
| **Reporting** | Rich dashboards, sender reports, boards | Basic API responses | Gmail ✓✓ |
| **Cleanup Rules** | DB-backed editable rules engine | API endpoints (no rule abstraction) | Gmail ✓✓ |
| **Bulk Actions** | Spam board, unwanted board, large+old, dupes | State-based batch operations | Gmail ✓ |
| **Dedupe Detection** | SHA-256 attachment hashing | Not implemented | Gmail ✓ |
| **Export Capabilities** | CSV, JSON, (XLSX, PDF later) | Not implemented | Gmail ✓✓ |
| **Search/Query** | Gmail query library, editable | Filter API params | Gmail ✓ |
| **Sync Strategy** | Snapshot + incremental (historyId) | Discover → Download pipeline | Gmail ✓ (historyId ftw) |
| **Background Jobs** | Progress model for long tasks | Implied via RunLog | Gmail ✓ (explicit) |
| **Settings Management** | Admin-managed global settings | .env only | Gmail ✓ |
| **Quota Tracking** | Gmail quota with color-coded UI | Not implemented | Gmail ✓ |
| **Admin Dashboard** | Multi-board (spam, unwanted, large, dupes) | Not implemented | Gmail ✓✓ |
| **Management Commands** | Extensive CLI toolkit | manage.py only | Gmail ✓ |
| **Documentation Quality** | Comprehensive prompt | Good README + diagrams | BackDeezUp ✓ |
| **Proxy/Preview** | Video/image 720p proxies | Not implemented | Gmail ✓ |
| **Protected Lists** | Allow/deny sender/domain/label lists | Not implemented | Gmail ✓ |
| **Automation** | Scheduled sync/cleanup (OFF by default) | Not implemented | Gmail ✓ |
| **Scope Restrictions** | Disables features if scope missing | Not tracked | Gmail ✓ |
| **Modern Tooling** | Not specified | uv (Rust-based) ✓✓ | BackDeezUp ✓ |
| **Knowledge Graph** | Not implemented | graphify ✓✓ | BackDeezUp ✓ |

**Score**: Gmail Cleanup leads on **feature richness** and **admin UX**. BackDeezUp leads on **architecture clarity** and **modern tooling**.

---

## Architectural Philosophy

### Gmail Cleanup
- **Admin-first**: Django Admin is the control plane
- **Dashboard-centric**: Multiple specialized boards (spam, unwanted, large+old, duplicates)
- **Rule-based**: Editable cleanup rules with dry-run → confirm → execute flow
- **Reporting-heavy**: Materialized views, sender reports, quota tracking
- **Human-in-the-loop**: Designed for manual review and bulk actions

### BackDeezUp
- **API-first**: Django Ninja endpoints are the primary interface
- **State-machine-centric**: Explicit 6-stage pipeline (DISCOVERED → DELETED)
- **Two-proof deletion**: File exists + DB record = safe to delete
- **Minimal UI**: Admin exists but is not the primary workflow
- **Automation-friendly**: Designed for programmatic batch operations

---

## Pros & Cons

### Gmail Cleanup Strengths
✅ **Rich reporting**: Sender analysis, attachment analysis, quota tracking  
✅ **Bulk cleanup workflows**: Pre-built boards for spam, promotions, large files  
✅ **Editable rule engine**: DB-backed queries with dry-run → execute flow  
✅ **Multi-account explicitly supported**: Per-account OAuth, scope tracking  
✅ **Export capabilities**: CSV, JSON for reports  
✅ **Protected lists**: Global allow/deny for senders/domains/labels  
✅ **Incremental sync**: Uses Gmail historyId for efficient updates  
✅ **Admin UX**: Dashboard landing page with color-coded quota  

### Gmail Cleanup Weaknesses
⚠️ **Domain-specific**: Gmail only (not Drive/Photos)  
⚠️ **No modern tooling**: No mention of uv, ruff, etc.  
⚠️ **Complex scope**: Feature-rich = more surface area for bugs  
⚠️ **No knowledge graph**: No codebase navigation aid  

### BackDeezUp Strengths
✅ **Clear state machine**: 6 explicit stages with transitions  
✅ **Two-proof deletion**: Stronger safety guarantees  
✅ **Modern tooling**: uv, pyproject.toml, dev.sh/dev.ps1  
✅ **Knowledge graph**: graphify for codebase navigation  
✅ **Good docs**: Mermaid diagrams, clear README  
✅ **API-first**: Clean separation of concerns  

### BackDeezUp Weaknesses
⚠️ **No reporting layer**: Missing dashboards, sender analysis, quota tracking  
⚠️ **No cleanup rules**: API endpoints but no abstraction for reusable queries  
⚠️ **No dedupe detection**: Missing SHA-256 attachment hashing  
⚠️ **No export**: No CSV/JSON export for reports  
⚠️ **No bulk actions UI**: Admin exists but is minimal  
⚠️ **No incremental sync**: Full discover each time (no historyId equivalent)  
⚠️ **No automation**: No scheduled sync/cleanup  

---

## Overlap Analysis

Both projects share:
- ✅ Django + Django Ninja + Swagger
- ✅ PostgreSQL (BackDeezUp supports SQLite fallback)
- ✅ Google user OAuth (no service accounts)
- ✅ Local file storage for backups
- ✅ Safety-first deletion philosophy
- ✅ Audit logging (different implementations)
- ✅ Port 8844 (interesting coincidence!)
- ✅ .env configuration
- ✅ State tracking (different approaches)
- ✅ Dry-run capabilities
- ✅ Admin interface (different emphasis)

---

## Blending Strategy: "Best of Both Worlds"

To transform BackDeezUp into the **ultimate Google data backup & cleanup platform**, adopt these Gmail Cleanup features:

### Phase 1: Foundation Enhancements (HIGH PRIORITY)
1. **Multi-account explicit support**
   - Add `GoogleAccount` model with slug, email, scopes, token_path, last_sync
   - Track granted scopes per account
   - Show scope warnings in admin (e.g., "permanent delete disabled: mail.google.com scope missing")

2. **Audit log enhancement**
   - Expand `RunLog` to track actor, action, dry_run flag, affected_count, affected_bytes, sample IDs
   - Make immutable from UI perspective
   - Add audit export (CSV/JSON)

3. **Settings management**
   - Move from .env-only to DB-backed settings model
   - Add admin page for global settings (automation kill switch, batch size, retention days, protected lists)

### Phase 2: Reporting & Dashboards (HIGH VALUE)
4. **Admin dashboard landing page**
   - Total assets discovered/downloaded/imported/verified/deleted
   - Total bytes backed up, total bytes in Drive/Photos
   - Recent sync status
   - Top file types by count/bytes
   - Quick links to cleanup boards

5. **Reporting models**
   - Materialized views or report tables for:
     - By file type (MIME type)
     - By size bucket (<1MB, 1-10MB, 10-100MB, 100MB-1GB, >1GB)
     - By age bucket (<30d, 30-90d, 90-180d, 180-360d, >360d)
     - By source (Drive vs Photos)
   - Rebuild command: `python manage.py rebuild_reports`

6. **Export capabilities**
   - CSV/JSON export for asset lists
   - Export filters: state, date range, file type, size range

### Phase 3: Cleanup Rules Engine (GAME CHANGER)
7. **CleanupRule model**
   ```python
   class CleanupRule(models.Model):
       name = CharField(max_length=200)
       description = TextField()
       query_filter = JSONField()  # {"mime_type__startswith": "video/", "size_bytes__gte": 100MB}
       min_age_days = IntegerField(default=360)
       action = CharField(choices=["trash", "hard_delete", "label"])
       enabled = BooleanField(default=False)
       dry_run_default = BooleanField(default=True)
       require_confirmation = BooleanField(default=True)
       account = ForeignKey(GoogleAccount, null=True)  # null = all accounts
       protected_mimetypes = JSONField(default=list)
       last_run_at = DateTimeField(null=True)
       last_dry_run_count = IntegerField(default=0)
       last_dry_run_bytes = BigIntegerField(default=0)
   ```

8. **Cleanup boards in admin**
   - **Large + Old Board**: >25MB older than 360d, >10MB with attachments
   - **Video Board**: mp4/mkv/mov older than 360d
   - **Duplicates Board**: SHA-256 hash detection (new feature!)
   - Each board shows: count, estimated bytes, checkbox, dry-run button, execute button

### Phase 4: Dedupe & Advanced Features
9. **SHA-256 deduplication**
   - Add `sha256` field to `MediaItem` (already has it in model?)
   - Add `DuplicateReport` model or materialized view
   - Show duplicate files grouped by hash with total duplicate bytes

10. **Incremental sync equivalent**
    - Drive API: use `changes.list()` with `pageToken` (like Gmail historyId)
    - Photos API: track `lastSyncTime`, use `mediaItems.search()` with date filters
    - Store checkpoint in `GoogleAccount.last_sync_token`

11. **Proxy/preview generation**
    - For images: generate 720p thumbnails (Pillow)
    - For videos: use ffmpeg (if available) to create preview clips
    - Store proxy path in `MediaItem.proxy_path`
    - Gracefully skip if ffmpeg missing

### Phase 5: Automation & Polish
12. **Scheduled jobs**
    - Add `django-apscheduler` or Celery
    - Scheduled sync (OFF by default)
    - Scheduled cleanup rules (OFF by default)
    - Admin toggle to enable

13. **Protected lists**
    - Add `ProtectedItem` model for file types, paths, or IDs that should never be deleted
    - Enforce in cleanup rule engine

14. **Quota tracking**
    - Fetch Drive quota via Drive API (`about.get(fields='storageQuota')`)
    - Store in `GoogleAccount.quota_total`, `quota_used`
    - Display in dashboard with color coding (green < 80%, yellow 80-95%, red > 95%)

---

## Concrete Changes Needed in BackDeezUp

### Models to Add/Modify

```python
# NEW MODEL
class GoogleAccount(models.Model):
    slug = CharField(max_length=50, unique=True)
    email = EmailField()
    token_path = CharField(max_length=255)
    granted_scopes = JSONField(default=list)
    last_sync_at = DateTimeField(null=True)
    last_sync_token = CharField(max_length=255, null=True)  # Drive pageToken or Photos date
    quota_total = BigIntegerField(null=True)
    quota_used = BigIntegerField(null=True)
    connected_at = DateTimeField(auto_now_add=True)

# NEW MODEL
class CleanupRule(models.Model):
    name = CharField(max_length=200)
    description = TextField()
    query_filter = JSONField()  # Django ORM filter kwargs
    min_age_days = IntegerField(default=360)
    action = CharField(max_length=20, choices=[("trash", "Trash"), ("hard", "Hard Delete")])
    enabled = BooleanField(default=False)
    dry_run_default = BooleanField(default=True)
    require_confirmation = BooleanField(default=True)
    account = ForeignKey(GoogleAccount, null=True, blank=True)
    protected_mimetypes = JSONField(default=list)
    last_run_at = DateTimeField(null=True)
    last_dry_run_count = IntegerField(default=0)
    last_dry_run_bytes = BigIntegerField(default=0)
    created_by = ForeignKey(User, related_name="rules_created")
    updated_by = ForeignKey(User, related_name="rules_updated")

# ENHANCE EXISTING
class RunLog(models.Model):
    # Add these fields:
    actor = ForeignKey(User, null=True)
    action = CharField(max_length=50)  # "sync_discover", "sync_download", "cleanup_rule", etc.
    dry_run = BooleanField(default=False)
    affected_count = IntegerField(default=0)
    affected_bytes = BigIntegerField(default=0)
    sample_ids = JSONField(default=list)  # Store up to 10 sample Drive IDs for audit

# ENHANCE EXISTING
class MediaItem(models.Model):
    # Add these fields (SHA-256 already exists!):
    proxy_path = CharField(max_length=500, null=True, blank=True)
    proxy_status = CharField(max_length=20, choices=[("pending", "Pending"), ("generated", "Generated"), ("skipped", "Skipped"), ("failed", "Failed")])

# ENHANCE EXISTING
class DriveAsset(models.Model):
    # Add FK to GoogleAccount:
    account = ForeignKey(GoogleAccount, on_delete=CASCADE, null=True)
```

### Admin Enhancements

```python
# backend_django/google_media_backup/admin.py

from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Sum, Count

@admin.register(GoogleAccount)
class GoogleAccountAdmin(admin.ModelAdmin):
    list_display = ["email", "slug", "quota_display", "last_sync_at", "connected_at"]
    readonly_fields = ["granted_scopes", "connected_at"]
    
    def quota_display(self, obj):
        if obj.quota_total and obj.quota_used:
            pct = (obj.quota_used / obj.quota_total) * 100
            color = "green" if pct < 80 else "orange" if pct < 95 else "red"
            return f"<span style='color:{color}'>{pct:.1f}%</span>"
        return "—"
    quota_display.allow_tags = True

@admin.register(CleanupRule)
class CleanupRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "action", "enabled", "min_age_days", "last_run_at", "last_dry_run_count"]
    list_filter = ["enabled", "action", "account"]
    actions = ["run_dry_run", "run_execute"]
    
    def run_dry_run(self, request, queryset):
        # Call cleanup rule engine with dry_run=True
        pass
    
    def run_execute(self, request, queryset):
        # Require confirmation, then call cleanup rule engine
        pass

# NEW: Dashboard view
class DashboardAdmin(admin.ModelAdmin):
    def get_urls(self):
        return [
            path("dashboard/", self.admin_site.admin_view(self.dashboard_view), name="dashboard"),
        ] + super().get_urls()
    
    def dashboard_view(self, request):
        stats = {
            "total_accounts": GoogleAccount.objects.count(),
            "total_assets": DriveAsset.objects.count(),
            "total_backed_up": MediaItem.objects.count(),
            "total_bytes": MediaItem.objects.aggregate(Sum("file__size"))["file__size__sum"] or 0,
            "assets_by_state": DriveAsset.objects.values("state").annotate(count=Count("id")),
            "top_mimetypes": DriveAsset.objects.values("mime_type").annotate(
                count=Count("id"),
                total_bytes=Sum("size_bytes")
            ).order_by("-total_bytes")[:10],
        }
        return render(request, "admin/dashboard.html", {"stats": stats})
```

### API Enhancements

```python
# backend_django/google_media_backup/api.py

from ninja import Router

cleanup_router = Router()

@cleanup_router.post("/rules/{rule_id}/dry-run")
def cleanup_dry_run(request, rule_id: int):
    rule = CleanupRule.objects.get(id=rule_id)
    # Query DriveAsset with rule.query_filter
    # Apply min_age_days filter
    # Return count and estimated bytes
    return {"count": 123, "estimated_bytes": 456789, "sample_assets": [...]}

@cleanup_router.post("/rules/{rule_id}/execute")
def cleanup_execute(request, rule_id: int, confirmation: str):
    # Check confirmation matches expected phrase
    # Run cleanup rule
    # Create RunLog entry
    # Return result
    return {"deleted": 123, "bytes_freed": 456789}

@cleanup_router.get("/reports/duplicates")
def duplicates_report(request):
    # Group MediaItem by sha256, filter count > 1
    # Return duplicate groups with total bytes
    return {"duplicates": [...]}

@cleanup_router.get("/reports/export")
def export_report(request, format: str = "csv"):
    # Export DriveAsset list as CSV or JSON
    pass
```

### Management Commands to Add

```bash
python manage.py sync_incremental --account=myaccount
python manage.py rebuild_reports
python manage.py cleanup_dry_run --rule=1
python manage.py cleanup_execute --rule=1 --confirm="YES DELETE"
python manage.py generate_proxies --limit=100
python manage.py check_quotas
python manage.py export_audit_log --start=2024-01-01 --format=csv
```

---

## Migration Path

### Step 1: Core Infrastructure (Week 1)
- [ ] Add `GoogleAccount` model + migration
- [ ] Add `CleanupRule` model + migration
- [ ] Enhance `RunLog` with audit fields + migration
- [ ] Add `account` FK to `DriveAsset` + migration
- [ ] Add `proxy_path` to `MediaItem` + migration

### Step 2: Reporting Foundation (Week 2)
- [ ] Create materialized view or report table for file type analysis
- [ ] Create materialized view for size/age bucket analysis
- [ ] Add `rebuild_reports` management command
- [ ] Add CSV/JSON export API endpoints

### Step 3: Admin Dashboard (Week 2-3)
- [ ] Create dashboard template with stats cards
- [ ] Add quota display with color coding
- [ ] Register new models in admin
- [ ] Add cleanup board views (large+old, video, duplicates)

### Step 4: Cleanup Rules Engine (Week 3-4)
- [ ] Implement cleanup rule query engine
- [ ] Add dry-run API endpoint
- [ ] Add execute API endpoint with confirmation
- [ ] Seed database with example rules
- [ ] Add protected lists enforcement

### Step 5: Advanced Features (Week 4-5)
- [ ] Implement SHA-256 duplicate detection
- [ ] Add incremental sync with Drive `changes.list()`
- [ ] Add proxy generation (Pillow for images, ffmpeg for video)
- [ ] Add quota tracking API integration

### Step 6: Automation (Week 5-6)
- [ ] Add django-apscheduler or Celery
- [ ] Create scheduled sync job (OFF by default)
- [ ] Create scheduled cleanup job (OFF by default)
- [ ] Add admin toggles for automation

---

## Final Recommendation

**Adopt from Gmail Cleanup:**
1. ✅ **Multi-account model** with scope tracking
2. ✅ **Rich admin dashboard** with boards
3. ✅ **Cleanup rules engine** with dry-run → execute flow
4. ✅ **Reporting layer** with materialized views
5. ✅ **Export capabilities** (CSV/JSON)
6. ✅ **Dedupe detection** via SHA-256
7. ✅ **Incremental sync** using Drive/Photos APIs
8. ✅ **Quota tracking** with color-coded UI
9. ✅ **Protected lists** for safety
10. ✅ **Enhanced audit logs** (actor, action, sample IDs)

**Keep from BackDeezUp:**
1. ✅ **Explicit state machine** (6 stages)
2. ✅ **Two-proof deletion** guards
3. ✅ **Modern tooling** (uv, pyproject.toml)
4. ✅ **Knowledge graph** (graphify)
5. ✅ **API-first architecture** (don't abandon it!)
6. ✅ **Clear documentation** with Mermaid diagrams

**Result:** A **hybrid platform** that is:
- **API-first** but **admin-rich**
- **State-machine-driven** but **rule-enhanced**
- **Safety-first** with **two-proof + dry-run + rules**
- **Modern tooling** with **enterprise features**

This becomes the **ultimate Google data backup & cleanup platform** that handles Drive, Photos, and (if expanded) Gmail in one unified codebase.
