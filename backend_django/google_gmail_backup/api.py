import uuid
from typing import List, Optional
import datetime as dt

from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from ninja import NinjaAPI, Schema, Query
from ninja.security import django_auth
from googleapiclient.errors import HttpError

from .models import CleanupRule, GmailMessage, GmailSyncState
from .services_gmail import (
    get_authenticated_email,
    list_message_ids,
    get_message_metadata,
    get_message_raw,
    extract_headers,
    has_attachments,
    parse_date,
    eml_path,
    sha256_bytes,
    trash_message,
    modify_labels,
    list_history,
)

gmail_api = NinjaAPI(urls_namespace="gmail", docs_url="/docs", auth=django_auth)


# ── Schemas ───────────────────────────────────────────────────────────────────

class GmailMessageOut(Schema):
    id: int
    gmail_id: str
    thread_id: str
    subject: str
    from_address: str
    date: Optional[dt.datetime] = None
    snippet: str
    labels: list
    size_estimate: int
    has_attachments: bool
    state: str
    error: Optional[str] = None


class GmailFilterIn(Schema):
    state: Optional[str] = None
    q: Optional[str] = None
    account_email: Optional[str] = None


class SyncResult(Schema):
    discovered: int = 0
    downloaded: int = 0
    errors: int = 0
    run_id: str
    sync_type: str = "full"


# ── Auth / profile ────────────────────────────────────────────────────────────

@gmail_api.get("/profile")
def gmail_profile(request):
    email = get_authenticated_email()
    if not email:
        return {"error": "Not authenticated. Run POST /api/drive/auth/connect first."}
    state, _ = GmailSyncState.objects.get_or_create(email=email)
    return {
        "email": email,
        "last_history_id": state.last_history_id,
        "last_full_sync_at": state.last_full_sync_at,
        "last_incremental_at": state.last_incremental_at,
        "total_messages": state.total_messages,
    }


# ── Discovery ─────────────────────────────────────────────────────────────────

@gmail_api.post("/sync/discover")
@ratelimit(key="user", rate="5/h", block=True)
def gmail_discover(request, q: str = "", max_pages: int = 20, page_size: int = 500):
    """
    Fast discovery — stores only message IDs (no per-message API calls).
    Metadata is fetched lazily during gmail-download.
    One list page = 1 API call regardless of page_size.
    """
    run_id = str(uuid.uuid4())
    account_email = get_authenticated_email()
    if not account_email:
        return {"error": "Not authenticated."}

    discovered = 0
    page_token = None
    pages = 0

    while pages < max_pages:
        ids, page_token = list_message_ids(
            page_token=page_token, q_filter=q, max_results=min(page_size, 500)
        )
        # Single query for entire page — avoids N+1 exists() per message ID
        page_ids = [m["id"] for m in ids]
        existing = set(
            GmailMessage.objects.filter(gmail_id__in=page_ids).values_list("gmail_id", flat=True)
        )
        new_ids = [mid for mid in page_ids if mid not in existing]
        if new_ids:
            GmailMessage.objects.bulk_create([
                GmailMessage(
                    gmail_id=mid,
                    thread_id="",
                    account_email=account_email,
                    state=GmailMessage.STATE_DISCOVERED,
                )
                for mid in new_ids
            ], ignore_conflicts=True)
            discovered += len(new_ids)
        pages += 1
        if not page_token:
            break

    state, _ = GmailSyncState.objects.get_or_create(email=account_email)
    state.last_full_sync_at = timezone.now()
    state.total_messages = GmailMessage.objects.filter(account_email=account_email).count()
    state.save()

    return {"discovered": discovered, "run_id": run_id, "sync_type": "full"}


@gmail_api.post("/sync/incremental")
def gmail_incremental(request):
    """
    Incremental sync using historyId. Falls back to full discover on 404.
    """
    account_email = get_authenticated_email()
    if not account_email:
        return {"error": "Not authenticated."}

    state, _ = GmailSyncState.objects.get_or_create(email=account_email)
    if not state.last_history_id:
        return {"error": "No historyId stored. Run POST /gmail/sync/discover first."}

    added = 0
    deleted = 0
    errors = 0
    run_id = str(uuid.uuid4())

    try:
        history_records, new_history_id = list_history(
            state.last_history_id,
            history_types=["messageAdded", "messageDeleted", "labelAdded", "labelRemoved"],
        )
    except HttpError as e:
        if e.resp.status == 404:
            return {
                "error": "historyId expired (>7 days). Run POST /gmail/sync/discover for full sync.",
                "run_id": run_id,
            }
        raise

    for record in history_records:
        for msg_added in record.get("messagesAdded", []):
            msg_id = msg_added["message"]["id"]
            if GmailMessage.objects.filter(gmail_id=msg_id).exists():
                continue
            try:
                msg = get_message_metadata(msg_id)
                if not msg:
                    errors += 1
                    continue
                headers = extract_headers(msg)
                date = parse_date(headers["date"])
                GmailMessage.objects.create(
                    gmail_id=msg_id,
                    thread_id=msg.get("threadId", ""),
                    history_id=msg.get("historyId"),
                    subject=headers["subject"],
                    from_address=headers["from"],
                    to_address=headers["to"],
                    date=date,
                    snippet=msg.get("snippet", ""),
                    labels=msg.get("labelIds", []),
                    size_estimate=msg.get("sizeEstimate", 0),
                    has_attachments=has_attachments(msg),
                    state=GmailMessage.STATE_DISCOVERED,
                    account_email=account_email,
                )
                added += 1
            except Exception:
                errors += 1

        for msg_deleted in record.get("messagesDeleted", []):
            msg_id = msg_deleted["message"]["id"]
            GmailMessage.objects.filter(gmail_id=msg_id).update(
                state=GmailMessage.STATE_DELETED
            )
            deleted += 1

        for label_change in record.get("labelsAdded", []) + record.get("labelsRemoved", []):
            msg_id = label_change["message"]["id"]
            new_labels = label_change["message"].get("labelIds", [])
            GmailMessage.objects.filter(gmail_id=msg_id).update(labels=new_labels)

    if new_history_id:
        state.last_history_id = new_history_id
    state.last_incremental_at = timezone.now()
    state.total_messages = GmailMessage.objects.filter(account_email=account_email).count()
    state.save()

    return {
        "added": added,
        "deleted": deleted,
        "errors": errors,
        "run_id": run_id,
        "sync_type": "incremental",
    }


# ── Download (.eml) ───────────────────────────────────────────────────────────

@gmail_api.post("/sync/download")
def gmail_download(request, limit: int = 20):
    """
    Download raw .eml for DISCOVERED messages. Stores to disk, updates state to DOWNLOADED.
    """
    qs = GmailMessage.objects.filter(
        state=GmailMessage.STATE_DISCOVERED
    ).order_by("discovered_at")[:limit]

    downloaded = 0
    errors = 0

    for msg in qs:
        try:
            # Fetch metadata if not yet populated (fast discover skips this)
            if not msg.subject and not msg.from_address:
                meta = get_message_metadata(msg.gmail_id)
                if meta:
                    headers = extract_headers(meta)
                    msg.thread_id = meta.get("threadId", "")
                    msg.history_id = meta.get("historyId")
                    msg.subject = headers["subject"]
                    msg.from_address = headers["from"]
                    msg.to_address = headers["to"]
                    msg.date = parse_date(headers["date"])
                    msg.snippet = meta.get("snippet", "")
                    msg.labels = meta.get("labelIds", [])
                    msg.size_estimate = meta.get("sizeEstimate", 0)
                    msg.has_attachments = has_attachments(meta)

            raw = get_message_raw(msg.gmail_id)
            if not raw:
                msg.error = "Empty raw response"
                msg.last_attempt_at = timezone.now()
                msg.save(update_fields=["error", "last_attempt_at"])
                errors += 1
                continue

            path = eml_path(msg.account_email, msg.date, msg.gmail_id)
            with open(path, "wb") as f:
                f.write(raw)

            msg.raw_path = path
            msg.sha256 = sha256_bytes(raw)
            msg.downloaded_at = timezone.now()
            msg.state = GmailMessage.STATE_DOWNLOADED
            msg.error = None
            msg.save(update_fields=[
                "thread_id", "history_id", "subject", "from_address", "to_address",
                "date", "snippet", "labels", "size_estimate", "has_attachments",
                "raw_path", "sha256", "downloaded_at", "state", "error",
            ])
            downloaded += 1
        except Exception as e:
            msg.error = str(e)
            msg.last_attempt_at = timezone.now()
            msg.save(update_fields=["error", "last_attempt_at"])
            errors += 1

    return {"downloaded": downloaded, "errors": errors}


# ── Verify ────────────────────────────────────────────────────────────────────

@gmail_api.post("/sync/verify")
def gmail_verify(request, limit: int = 50):
    """Verify .eml file exists on disk for DOWNLOADED messages."""
    import os
    qs = GmailMessage.objects.filter(
        state=GmailMessage.STATE_DOWNLOADED
    ).order_by("downloaded_at")[:limit]

    verified = 0
    failed = 0

    for msg in qs:
        if msg.raw_path and os.path.exists(msg.raw_path):
            msg.state = GmailMessage.STATE_VERIFIED
            msg.error = None
            msg.save(update_fields=["state", "error"])
            verified += 1
        else:
            msg.error = "Local .eml file missing"
            msg.save(update_fields=["error"])
            failed += 1

    return {"verified": verified, "failed": failed}


# ── Cleanup actions ───────────────────────────────────────────────────────────

@gmail_api.post("/cleanup/trash")
def gmail_trash(request, gmail_ids: List[str], dry_run: bool = True):
    """
    Trash messages in Gmail. Dry-run by default — pass dry_run=false to execute.
    """
    if dry_run:
        count = GmailMessage.objects.filter(gmail_id__in=gmail_ids).count()
        return {"dry_run": True, "would_trash": count, "ids": gmail_ids}

    trashed = 0
    errors = 0
    for gmail_id in gmail_ids:
        if trash_message(gmail_id):
            GmailMessage.objects.filter(gmail_id=gmail_id).update(
                state=GmailMessage.STATE_TRASHED
            )
            trashed += 1
        else:
            errors += 1

    return {"dry_run": False, "trashed": trashed, "errors": errors}


@gmail_api.post("/cleanup/label")
def gmail_label(request, gmail_ids: List[str], add_labels: List[str] = [], remove_labels: List[str] = [], dry_run: bool = True):
    if dry_run:
        return {"dry_run": True, "would_modify": len(gmail_ids), "add": add_labels, "remove": remove_labels}

    modified = 0
    errors = 0
    for gmail_id in gmail_ids:
        if modify_labels(gmail_id, add_labels=add_labels or None, remove_labels=remove_labels or None):
            modified += 1
        else:
            errors += 1

    return {"dry_run": False, "modified": modified, "errors": errors}


# ── Progress ──────────────────────────────────────────────────────────────────

@gmail_api.get("/progress")
def gmail_progress(request):
    from django.db.models import Count, Sum
    counts = dict(GmailMessage.objects.values_list("state").annotate(n=Count("id")))
    total_db = sum(counts.values()) or 0
    sync_total = GmailSyncState.objects.aggregate(t=Sum("total_messages"))["t"] or total_db
    verified = counts.get(GmailMessage.STATE_VERIFIED, 0)
    downloaded = counts.get(GmailMessage.STATE_DOWNLOADED, 0)
    discovered = counts.get(GmailMessage.STATE_DISCOVERED, 0)
    pct = round(verified / sync_total * 100, 1) if sync_total else 0
    filled = int(pct / 5)
    bar = "=" * filled + "-" * (20 - filled)
    return {
        "total": sync_total,
        "discovered": discovered,
        "downloaded": downloaded,
        "verified": verified,
        "pct": pct,
        "bar": f"[{bar}] {pct}% ({verified}/{sync_total} verified)",
    }


# ── Asset listing ─────────────────────────────────────────────────────────────

@gmail_api.get("/messages", response=List[GmailMessageOut])
def list_messages(request, filters: GmailFilterIn = Query(...)):
    qs = GmailMessage.objects.all().order_by("-date")
    if filters.state:
        qs = qs.filter(state=filters.state)
    if filters.q:
        qs = qs.filter(subject__icontains=filters.q) | qs.filter(from_address__icontains=filters.q)
    if filters.account_email:
        qs = qs.filter(account_email=filters.account_email)
    return list(qs[:500])


# ── Cleanup rules API ─────────────────────────────────────────────────────────

@gmail_api.get("/rules")
def list_rules(request):
    from .models import CleanupRule
    rules = CleanupRule.objects.all().order_by("name")
    return [
        {
            "id": r.id, "name": r.name, "action": r.action,
            "gmail_query": r.gmail_query, "min_age_days": r.min_age_days,
            "enabled": r.enabled, "last_run_at": r.last_run_at,
            "last_dry_run_count": r.last_dry_run_count,
            "last_affected_count": r.last_affected_count,
        }
        for r in rules
    ]


@gmail_api.post("/rules/{rule_id}/dry-run")
def rule_dry_run(request, rule_id: int):
    from .models import CleanupRule
    from .services_rules import apply_rule
    rule = CleanupRule.objects.get(id=rule_id)
    audit = apply_rule(rule, dry_run=True, actor_label="api")
    return {
        "rule": rule.name, "dry_run": True,
        "would_affect": audit.affected_count,
        "sample_subjects": audit.sample_subjects,
    }


@gmail_api.post("/rules/{rule_id}/execute")
@ratelimit(key="user", rate="10/h", block=True)
def rule_execute(request, rule_id: int):
    from .models import CleanupRule
    from .services_rules import apply_rule
    rule = CleanupRule.objects.get(id=rule_id)
    audit = apply_rule(rule, dry_run=False, actor_label="api")
    return {
        "rule": rule.name, "dry_run": False,
        "affected": audit.affected_count,
        "status": audit.status,
    }


@gmail_api.post("/rules/run-all")
@ratelimit(key="user", rate="3/h", block=True)
def rules_run_all(request, dry_run: bool = True):
    from .services_rules import run_all_enabled_rules
    results = run_all_enabled_rules(dry_run=dry_run, actor_label="api")
    return [
        {"rule": a.rule_name, "affected": a.affected_count, "status": a.status}
        for a in results
    ]


@gmail_api.post("/protected-senders/apply")
def apply_protected_senders(request):
    from .services_rules import apply_protected_sender_rules
    audit = apply_protected_sender_rules()
    return {"affected": audit.affected_count, "status": audit.status}


@gmail_api.get("/audit-log")
def get_audit_log(request, limit: int = 50):
    from .models import CleanupAuditLog
    logs = CleanupAuditLog.objects.order_by("-started_at")[:limit]
    return [
        {
            "id": a.id, "rule": a.rule_name, "action": a.action,
            "dry_run": a.dry_run, "affected": a.affected_count,
            "status": a.status, "actor": a.actor_label,
            "started_at": str(a.started_at), "finished_at": str(a.finished_at),
        }
        for a in logs
    ]


# ── Rule builder API ─────────────────────────────────────────────────────────

@gmail_api.post("/rule-builder/preview")
def rule_builder_preview(request):
    """
    POST body: {"conditions": [...], "action": "trash", "min_age_days": 30}
    Returns the compiled Gmail query string (no DB write, no Gmail API call).
    """
    import json as _json
    from .query_compiler import preview_query
    try:
        body = _json.loads(request.body)
    except Exception:
        return {"error": "Invalid JSON"}
    conditions = body.get("conditions", [])
    query = preview_query(conditions)
    return {"query": query, "condition_count": len(conditions)}


@gmail_api.post("/rule-builder/dry-run")
def rule_builder_dry_run(request):
    """
    POST body: {"conditions": [...], "action": "trash", "min_age_days": 30, "name": "My Rule"}
    Compiles query, counts matching local messages, returns sample subjects.
    No DB write, no Gmail API call.
    """
    import json as _json
    from datetime import timedelta
    from .query_compiler import preview_query
    try:
        body = _json.loads(request.body)
    except Exception:
        return {"error": "Invalid JSON"}
    conditions = body.get("conditions", [])
    min_age = int(body.get("min_age_days", 0))
    query = preview_query(conditions)
    qs = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED)
    if min_age:
        cutoff = timezone.now() - timedelta(days=min_age)
        qs = qs.filter(date__lte=cutoff)
    count = qs.count()
    samples = list(qs.values_list("subject", "from_address")[:10])
    return {
        "query": query,
        "match_count": count,
        "samples": [{"subject": s, "from": f} for s, f in samples],
    }


@gmail_api.post("/rule-builder/save")
def rule_builder_save(request):
    """
    POST body: {
        "name": "LinkedIn jobs", "description": "...",
        "action": "label", "label_name": "work/jobs",
        "min_age_days": 0, "enabled": false,
        "conditions": [
            {"field": "sender", "operator": "contains", "value": "linkedin.com", "logic": "AND", "order": 1},
            {"field": "subject", "operator": "contains", "value": "job", "logic": "OR", "order": 2},
        ]
    }
    Creates CleanupRule + RuleCondition rows, compiles gmail_query.
    """
    import json as _json
    from .models import CleanupRule, RuleCondition
    from .query_compiler import preview_query
    try:
        body = _json.loads(request.body)
    except Exception:
        return {"error": "Invalid JSON"}

    name = body.get("name", "").strip()
    if not name:
        return {"error": "name is required"}

    conditions_data = body.get("conditions", [])
    compiled_query = preview_query(conditions_data)

    rule = CleanupRule.objects.create(
        name=name,
        description=body.get("description", ""),
        gmail_query=compiled_query,
        action=body.get("action", CleanupRule.ACTION_TRASH),
        label_name=body.get("label_name", ""),
        min_age_days=int(body.get("min_age_days", 0)),
        enabled=bool(body.get("enabled", False)),
        dry_run_default=True,
    )

    for i, cdata in enumerate(sorted(conditions_data, key=lambda x: x.get("order", i))):
        RuleCondition.objects.create(
            rule=rule,
            order=cdata.get("order", i),
            field=cdata.get("field", ""),
            operator=cdata.get("operator", ""),
            value=cdata.get("value", ""),
            logic=cdata.get("logic", "AND"),
        )

    return {
        "id": rule.id,
        "name": rule.name,
        "compiled_query": compiled_query,
        "condition_count": len(conditions_data),
        "enabled": rule.enabled,
    }


@gmail_api.get("/rule-builder/fields")
def rule_builder_fields(request):
    """Return field/operator/logic choices for the frontend builder."""
    from .models import RuleCondition as RC
    return {
        "fields": [{"value": v, "label": lbl} for v, lbl in RC.FIELD_CHOICES],
        "operators": [{"value": v, "label": lbl} for v, lbl in RC.OP_CHOICES],
        "logic": [{"value": v, "label": lbl} for v, lbl in RC.LOGIC_CHOICES],
        "actions": [{"value": v, "label": lbl} for v, lbl in CleanupRule.ACTION_CHOICES if hasattr(CleanupRule, 'ACTION_CHOICES')],
    }


# ── Empty Gmail Trash ─────────────────────────────────────────────────────────

@gmail_api.post("/ops/empty-trash")
def gmail_empty_trash(request, skip_backup_check: bool = False, dry_run: bool = True):
    """
    Permanently delete all messages in Gmail trash.
    dry_run=true (default): count only, no deletion.
    skip_backup_check=true: skip the ≥90% backup completeness guard.
    """
    from django.db.models import Sum
    from .models import CleanupAuditLog, GmailSyncState
    from .services_gmail import gmail_service

    svc = gmail_service()
    if not svc:
        return {"error": "Not authenticated. Run: make auth"}

    if not skip_backup_check:
        sync_total = GmailSyncState.objects.aggregate(t=Sum("total_messages"))["t"] or 0
        verified = GmailMessage.objects.filter(state=GmailMessage.STATE_VERIFIED).count()
        pct = round(verified / max(sync_total, 1) * 100, 1)
        if pct < 90:
            return {
                "blocked": True,
                "reason": f"Backup only {pct}% complete ({verified}/{sync_total}). Need ≥90%.",
                "pct": pct,
                "verified": verified,
                "sync_total": sync_total,
            }

    # Count trash
    trash_ids = []
    page_token = None
    while True:
        params = dict(userId="me", q="in:trash", maxResults=500)
        if page_token:
            params["pageToken"] = page_token
        res = svc.users().messages().list(**params).execute()
        trash_ids.extend([m["id"] for m in res.get("messages", [])])
        page_token = res.get("nextPageToken")
        if not page_token:
            break

    count = len(trash_ids)
    if dry_run:
        return {"dry_run": True, "trash_count": count,
                "message": f"Would permanently delete {count} messages. POST with dry_run=false to execute."}

    if count == 0:
        return {"deleted": 0, "message": "Gmail trash already empty."}

    audit = CleanupAuditLog.objects.create(
        rule=None, rule_name="Empty Gmail Trash",
        action="permanent_delete", dry_run=False,
        actor_label=f"web:{request.user.username}", status="RUNNING",
    )

    BATCH_SIZE = 1000
    deleted = errors = 0
    chunks = [trash_ids[i:i + BATCH_SIZE] for i in range(0, len(trash_ids), BATCH_SIZE)]
    for chunk in chunks:
        try:
            svc.users().messages().batchDelete(userId="me", body={"ids": chunk}).execute()
            deleted += len(chunk)
        except Exception as exc:
            errors += len(chunk)

    from django.utils import timezone
    audit.affected_count = deleted
    audit.affected_gmail_ids = trash_ids[:100]
    audit.affected_ids_truncated = len(trash_ids) > 100
    audit.status = "OK" if errors == 0 else "ERROR"
    audit.error_text = f"{errors} messages failed" if errors else ""
    audit.finished_at = timezone.now()
    audit.save()

    return {"deleted": deleted, "errors": errors, "dry_run": False}


# ── Export endpoints ──────────────────────────────────────────────────────────

AUDIT_FIELDS = [
    ("ID", "id"), ("Rule", "rule"), ("Action", "action"),
    ("Dry Run", "dry_run"), ("Affected", "affected"), ("Status", "status"),
    ("Actor", "actor"), ("Started", "started_at"), ("Finished", "finished_at"),
]

MSG_FIELDS = [
    ("Gmail ID", "gmail_id"), ("Subject", "subject"), ("From", "from_address"),
    ("Date", "date"), ("State", "state"), ("Labels", "labels"),
    ("Size", "size_estimate"), ("Has Attachments", "has_attachments"),
]


@gmail_api.get("/export/audit-log")
def export_audit_log(request, fmt: str = "csv", limit: int = 1000):
    from .models import CleanupAuditLog
    from .exports import export_queryset
    logs = CleanupAuditLog.objects.order_by("-started_at")[:limit]
    rows = [
        {"id": a.id, "rule": a.rule_name, "action": a.action,
         "dry_run": str(a.dry_run), "affected": a.affected_count,
         "status": a.status, "actor": a.actor_label,
         "started_at": str(a.started_at), "finished_at": str(a.finished_at)}
        for a in logs
    ]
    return export_queryset(request, rows, AUDIT_FIELDS, "audit_log", fmt)


@gmail_api.get("/export/messages")
def export_messages(request, fmt: str = "csv", state: str = "", limit: int = 1000):
    from .exports import export_queryset
    qs = GmailMessage.objects.all().order_by("-date")
    if state:
        qs = qs.filter(state=state)
    qs = qs[:limit]
    rows = [
        {"gmail_id": m.gmail_id, "subject": m.subject, "from_address": m.from_address,
         "date": str(m.date), "state": m.state, "labels": str(m.labels),
         "size_estimate": m.size_estimate, "has_attachments": str(m.has_attachments)}
        for m in qs
    ]
    name = f"gmail_messages{'_' + state if state else ''}"
    return export_queryset(request, rows, MSG_FIELDS, name, fmt)
