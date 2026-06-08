import base64
import hashlib
import logging
import os
from typing import Optional

from decouple import config
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_media_backup.services_google import _load_creds, _save_creds

log = logging.getLogger(__name__)

CLIENT_SECRETS = config("GOOGLE_CLIENT_SECRETS", default="secrets/google_client.json")
TOKEN_FILE_ENC = config("GOOGLE_TOKEN_FILE", default="secrets/google_token.json")


def gmail_service():
    creds = _load_creds()
    if not creds:
        log.warning("gmail_service: no credentials found — run make auth")
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
    scopes = getattr(creds, "scopes", None) or []
    if scopes and "https://www.googleapis.com/auth/gmail.modify" not in scopes:
        log.error("gmail_service: token missing gmail.modify scope — delete token and re-run make auth. Current scopes: %s", scopes)
    return build("gmail", "v1", credentials=creds)


def get_authenticated_email() -> Optional[str]:
    svc = gmail_service()
    if not svc:
        return None
    profile = svc.users().getProfile(userId="me").execute()
    return profile.get("emailAddress")


# ── Discovery ─────────────────────────────────────────────────────────────────

def list_message_ids(page_token=None, q_filter: str = "", max_results: int = 500):
    """
    Returns (list of {id, threadId}, nextPageToken).
    q_filter supports Gmail search syntax e.g. 'after:2024/01/01 has:attachment'.
    """
    svc = gmail_service()
    if not svc:
        return ([], None)
    params = dict(userId="me", maxResults=min(max_results, 500))
    if q_filter:
        params["q"] = q_filter
    if page_token:
        params["pageToken"] = page_token
    res = svc.users().messages().list(**params).execute()
    return (res.get("messages", []), res.get("nextPageToken"))


def get_message_metadata(msg_id: str) -> Optional[dict]:
    """Fetch metadata-only (no body) — cheap, 20 quota units."""
    svc = gmail_service()
    if not svc:
        return None
    return svc.users().messages().get(
        userId="me",
        id=msg_id,
        format="metadata",
        metadataHeaders=["Subject", "From", "To", "Date"],
    ).execute()


def get_message_full(msg_id: str) -> Optional[dict]:
    """Fetch full message including body."""
    svc = gmail_service()
    if not svc:
        return None
    return svc.users().messages().get(userId="me", id=msg_id, format="full").execute()


def get_message_raw(msg_id: str) -> Optional[bytes]:
    """Fetch raw RFC822 bytes (.eml format)."""
    svc = gmail_service()
    if not svc:
        return None
    res = svc.users().messages().get(userId="me", id=msg_id, format="raw").execute()
    raw = res.get("raw")
    if not raw:
        return None
    return base64.urlsafe_b64decode(raw + "==")


def get_attachment_data(msg_id: str, attachment_id: str) -> Optional[bytes]:
    svc = gmail_service()
    if not svc:
        return None
    res = svc.users().messages().attachments().get(
        userId="me", messageId=msg_id, id=attachment_id
    ).execute()
    data = res.get("data")
    if not data:
        return None
    return base64.urlsafe_b64decode(data + "==")


# ── Incremental sync ──────────────────────────────────────────────────────────

def list_history(start_history_id: str, history_types=None):
    """
    Returns (history_records, new_history_id) or raises Exception on 404.
    Caller must catch 404 and fall back to full sync.
    history_types: list of 'messageAdded', 'messageDeleted', 'labelAdded', 'labelRemoved'
    """
    svc = gmail_service()
    if not svc:
        return ([], None)
    params = dict(userId="me", startHistoryId=start_history_id, maxResults=500)
    if history_types:
        params["historyTypes"] = history_types
    res = svc.users().history().list(**params).execute()
    return (res.get("history", []), res.get("historyId"))


# ── Cleanup actions ───────────────────────────────────────────────────────────

def trash_message(msg_id: str, user_id: str = "me") -> bool:
    """Move a single message to Gmail trash. Logs errors instead of silently returning False."""
    svc = gmail_service()
    if not svc:
        return False
    try:
        svc.users().messages().trash(userId=user_id, id=msg_id).execute()
        return True
    except HttpError as exc:
        if exc.resp.status == 429:
            log.warning("Gmail quota exceeded trashing %s: %s", msg_id, exc)
        else:
            log.warning("Failed to trash message %s (HTTP %s): %s", msg_id, exc.resp.status, exc)
        return False
    except Exception as exc:
        log.error("Unexpected error trashing message %s: %s", msg_id, exc)
        return False


def batch_trash_messages(msg_ids: list, user_id: str = "me") -> int:
    """Trash multiple messages using Gmail batchModify. Returns count of successful trashes."""
    if not msg_ids:
        return 0
    svc = gmail_service()
    if not svc:
        return 0
    try:
        svc.users().messages().batchModify(
            userId=user_id,
            body={"ids": msg_ids, "addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
        ).execute()
        return len(msg_ids)
    except HttpError as exc:
        log.warning("batchModify trash failed (HTTP %s): %s", exc.resp.status, exc)
        return 0
    except Exception as exc:
        log.error("Unexpected error in batch trash: %s", exc)
        return 0


def delete_message_permanent(msg_id: str, user_id: str = "me") -> bool:
    """Permanently delete a message. Requires https://mail.google.com/ scope."""
    svc = gmail_service()
    if not svc:
        return False
    try:
        svc.users().messages().delete(userId=user_id, id=msg_id).execute()
        return True
    except HttpError as exc:
        log.warning("Failed to permanently delete %s (HTTP %s): %s", msg_id, exc.resp.status, exc)
        return False
    except Exception as exc:
        log.error("Unexpected error deleting message %s: %s", msg_id, exc)
        return False


def modify_labels(msg_id: str, add_labels=None, remove_labels=None, user_id: str = "me") -> bool:
    svc = gmail_service()
    if not svc:
        return False
    try:
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        svc.users().messages().modify(userId=user_id, id=msg_id, body=body).execute()
        return True
    except HttpError as exc:
        log.warning("Failed to modify labels on %s (HTTP %s): %s", msg_id, exc.resp.status, exc)
        return False
    except Exception as exc:
        log.error("Unexpected error modifying labels on %s: %s", msg_id, exc)
        return False


def batch_modify_labels(msg_ids: list, add_labels=None, remove_labels=None, user_id: str = "me") -> bool:
    """Apply label changes to multiple messages in one API call — O(1) instead of O(n)."""
    if not msg_ids:
        return True
    svc = gmail_service()
    if not svc:
        return False
    try:
        body: dict = {"ids": msg_ids}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        svc.users().messages().batchModify(userId=user_id, body=body).execute()
        return True
    except HttpError as exc:
        log.warning("batchModify labels failed (HTTP %s): %s", exc.resp.status, exc)
        return False
    except Exception as exc:
        log.error("Unexpected error in batch label modify: %s", exc)
        return False


# ── Storage helpers ───────────────────────────────────────────────────────────

def eml_dir(account_email: str, msg_date) -> str:
    """Returns the directory path for .eml storage. Does NOT create the directory."""
    from django.conf import settings
    year = msg_date.strftime("%Y") if msg_date else "unknown"
    month = msg_date.strftime("%m") if msg_date else "00"
    safe_email = account_email.replace("@", "_at_").replace(".", "_")
    return os.path.join(settings.MEDIA_ROOT, "gmail", safe_email, year, month)


def ensure_eml_path(account_email: str, msg_date, gmail_id: str) -> str:
    """Returns .eml path AND creates the directory. Use when writing files."""
    base = eml_dir(account_email, msg_date)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{gmail_id}.eml")


def eml_path(account_email: str, msg_date, gmail_id: str) -> str:
    """Alias for ensure_eml_path — kept for backward compatibility."""
    return ensure_eml_path(account_email, msg_date, gmail_id)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ── Header extraction helpers ─────────────────────────────────────────────────

def extract_headers(msg: dict) -> dict:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return {
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "date": headers.get("date", ""),
    }


def parse_date(date_str: str):
    """Parse RFC2822 date string to timezone-aware datetime. Returns None on failure."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        import datetime
        from django.utils import timezone
        dt = parsedate_to_datetime(date_str)
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt, datetime.timezone.utc)
        return dt
    except Exception:
        return None


def has_attachments(msg: dict) -> bool:
    parts = msg.get("payload", {}).get("parts", [])
    return any(p.get("filename") for p in parts)


def extract_attachment_metadata(msg: dict) -> list:
    parts = msg.get("payload", {}).get("parts", [])
    results = []
    for part in parts:
        if not part.get("filename"):
            continue
        body = part.get("body", {})
        results.append({
            "attachment_id": body.get("attachmentId", ""),
            "filename": part.get("filename", ""),
            "mime_type": part.get("mimeType", ""),
            "size": body.get("size", 0),
        })
    return results
