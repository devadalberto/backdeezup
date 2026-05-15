import uuid
from typing import List, Optional
import datetime as dt

from django.utils import timezone
from ninja import NinjaAPI, Schema, Query
from googleapiclient.errors import HttpError

from .models import GmailMessage, GmailSyncState
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

gmail_api = NinjaAPI(urls_namespace="gmail", docs_url="/docs")


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
def gmail_discover(request, q: str = "", max_pages: int = 10, page_size: int = 500):
    """
    Full snapshot discovery — lists all message IDs and fetches metadata.
    Stores each as a GmailMessage in DISCOVERED state.
    On completion stores the latest historyId for future incremental syncs.
    """
    run_id = str(uuid.uuid4())
    account_email = get_authenticated_email()
    if not account_email:
        return {"error": "Not authenticated."}

    discovered = 0
    errors = 0
    page_token = None
    pages = 0
    latest_history_id = None

    while pages < max_pages:
        ids, page_token = list_message_ids(page_token=page_token, q_filter=q, max_results=page_size)
        for msg_ref in ids:
            msg_id = msg_ref["id"]
            if GmailMessage.objects.filter(gmail_id=msg_id).exists():
                continue
            try:
                msg = get_message_metadata(msg_id)
                if not msg:
                    errors += 1
                    continue
                headers = extract_headers(msg)
                date = parse_date(headers["date"])
                GmailMessage.objects.get_or_create(
                    gmail_id=msg_id,
                    defaults=dict(
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
                    ),
                )
                if not latest_history_id:
                    latest_history_id = msg.get("historyId")
                discovered += 1
            except Exception:
                errors += 1

        pages += 1
        if not page_token:
            break

    # Update sync state
    state, _ = GmailSyncState.objects.get_or_create(email=account_email)
    state.last_full_sync_at = timezone.now()
    state.total_messages = GmailMessage.objects.filter(account_email=account_email).count()
    if latest_history_id:
        state.last_history_id = latest_history_id
    state.save()

    return {"discovered": discovered, "errors": errors, "run_id": run_id, "sync_type": "full"}


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
            msg.save(update_fields=["raw_path", "sha256", "downloaded_at", "state", "error"])
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
