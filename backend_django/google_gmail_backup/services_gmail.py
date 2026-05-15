import base64
import email
import hashlib
import json
import os
from typing import Optional

from decouple import config
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from google_media_backup.utils import get_fernet

# Gmail scopes — readonly for backup; modify for label/trash operations
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    # Full access required for permanent hard delete
    # "https://mail.google.com/",
]

CLIENT_SECRETS = config("GOOGLE_CLIENT_SECRETS", default="secrets/google_client.json")
TOKEN_FILE_ENC = config("GOOGLE_TOKEN_FILE", default="secrets/google_token.json")

# ── Credential helpers (reuses same encrypted token as Drive/Photos) ──────────

def _load_creds() -> Optional[Credentials]:
    if not os.path.exists(TOKEN_FILE_ENC):
        return None
    try:
        with open(TOKEN_FILE_ENC) as f:
            data = json.load(f)
        token_json = get_fernet().decrypt(data["payload"].encode()).decode()
        all_scopes = GMAIL_SCOPES + [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/photoslibrary.readonly",
        ]
        return Credentials.from_authorized_user_info(json.loads(token_json), all_scopes)
    except Exception:
        return None


def _save_creds(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(TOKEN_FILE_ENC), exist_ok=True)
    wrapped = {"payload": get_fernet().encrypt(creds.to_json().encode()).decode()}
    with open(TOKEN_FILE_ENC, "w") as f:
        json.dump(wrapped, f, indent=2)


def gmail_service():
    creds = _load_creds()
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
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

def trash_message(msg_id: str) -> bool:
    svc = gmail_service()
    if not svc:
        return False
    try:
        svc.users().messages().trash(userId="me", id=msg_id).execute()
        return True
    except Exception:
        return False


def delete_message_permanent(msg_id: str) -> bool:
    """Requires https://mail.google.com/ scope."""
    svc = gmail_service()
    if not svc:
        return False
    try:
        svc.users().messages().delete(userId="me", id=msg_id).execute()
        return True
    except Exception:
        return False


def modify_labels(msg_id: str, add_labels=None, remove_labels=None) -> bool:
    svc = gmail_service()
    if not svc:
        return False
    try:
        body = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        svc.users().messages().modify(userId="me", id=msg_id, body=body).execute()
        return True
    except Exception:
        return False


# ── Storage helpers ───────────────────────────────────────────────────────────

def eml_path(account_email: str, msg_date, gmail_id: str) -> str:
    """Returns deterministic .eml path: gmail/<account>/<year>/<month>/<gmail_id>.eml"""
    from django.conf import settings
    year = msg_date.strftime("%Y") if msg_date else "unknown"
    month = msg_date.strftime("%m") if msg_date else "00"
    safe_email = account_email.replace("@", "_at_").replace(".", "_")
    base = os.path.join(settings.MEDIA_ROOT, "gmail", safe_email, year, month)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"{gmail_id}.eml")


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
    """Parse RFC2822 date string to datetime. Returns None on failure."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
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
