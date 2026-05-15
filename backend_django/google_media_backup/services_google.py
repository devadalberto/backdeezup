import io, json, os
from typing import List, Tuple, Optional
from decouple import config
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from .utils import get_fernet

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

CLIENT_SECRETS = config('GOOGLE_CLIENT_SECRETS', default='secrets/google_client.json')
TOKEN_FILE_ENC = config('GOOGLE_TOKEN_FILE', default='secrets/google_token.json')
MIME_ALLOWLIST = [m.strip() for m in config('GOOGLE_MIME_ALLOWLIST', default='image/jpeg').split(',') if m.strip()]

def _load_creds() -> Optional[Credentials]:
    if not os.path.exists(TOKEN_FILE_ENC): return None
    try:
        with open(TOKEN_FILE_ENC) as f: data = json.load(f)
        token_json = get_fernet().decrypt(data['payload'].encode()).decode()
        return Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except Exception:
        return None

def _save_creds(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(TOKEN_FILE_ENC), exist_ok=True)
    wrapped = {'payload': get_fernet().encrypt(creds.to_json().encode()).decode()}
    with open(TOKEN_FILE_ENC, 'w') as f: json.dump(wrapped, f, indent=2)

def start_oauth_local() -> str:
    """
    Headless OAuth flow — prints a URL for the user to open in any browser.
    Works on servers with no display. Paste the redirected localhost URL back
    when prompted, or use run_local_server() on a machine with a browser.
    """
    if not os.path.exists(CLIENT_SECRETS):
        return "Missing client secrets at secrets/google_client.json"
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url, _ = flow.authorization_url(prompt="consent")
    print("\n" + "="*60)
    print("Open this URL in your browser:")
    print(auth_url)
    print("="*60)
    code = input("\nPaste the authorization code here: ").strip()
    flow.fetch_token(code=code)
    _save_creds(flow.credentials)
    return "OAuth completed and token saved."

def drive_service():
    creds = _load_creds()
    if not creds: return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request()); _save_creds(creds)
    return build('drive', 'v3', credentials=creds)

def list_media_files(page_size: int = 200, page_token: str | None = None):
    """
    Return one page of media-like files (images/videos or shortcuts to them).
    Looks across My Drive + Shared Drives and skips trashed.
    """
    svc = drive_service()
    if not svc:
        return ([], None)

    # Build a permissive query: any image/* or video/* or a shortcut to one.
    q_parts = [
        "(mimeType contains 'image/' or mimeType contains 'video/')",
        "trashed = false",
    ]
    # Also include shortcuts that point to media
    q_parts.append(
        "(mimeType = 'application/vnd.google-apps.shortcut' and "\
        "(shortcutDetails.targetMimeType contains 'image/' or "\
        " shortcutDetails.targetMimeType contains 'video/'))"
    )
    q = f"({q_parts[0]}) and {q_parts[1]} or ({q_parts[2]})"

    req = svc.files().list(
        pageSize=min(int(page_size or 200), 1000),
        pageToken=page_token,
        q=q,
        fields=(
            "nextPageToken,"
            "files(id,name,mimeType,size,md5Checksum,"
            "shortcutDetails/targetId,shortcutDetails/targetMimeType)"
        ),
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        corpora="user",  # change to 'allDrives' if you want org-wide search
        spaces="drive",
    )
    res = req.execute()
    return (res.get("files", []), res.get("nextPageToken"))


def photos_service():
    """Google Photos Library API client."""
    creds = _load_creds()
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request()); _save_creds(creds)
    # Photos requires discovery via HTTP; static_discovery=False lets googleapiclient fetch it
    return build("photoslibrary", "v1", credentials=creds, static_discovery=False)


def list_photos_items(page_size: int = 200, page_token: str | None = None):
    """
    Return mediaItems from Google Photos Library.
    Note: these are NOT Drive files; they’ll have different IDs.
    """
    svc = photos_service()
    if not svc:
        return ([], None)
    res = svc.mediaItems().list(
        pageSize=min(int(page_size or 200), 1000),
        pageToken=page_token,
    ).execute()
    return (res.get("mediaItems", []) or [], res.get("nextPageToken"))


# ---- Common “documents” in Drive (pdf/office/text/archives) ----
_COMMON_MIME_LIST = [
    # PDF
    "application/pdf",
    # MS Office
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # Text / CSV
    "text/plain",
    "text/csv",
    # Archives
    "application/zip",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    # Apple iWork
    "application/vnd.apple.pages",
    "application/vnd.apple.numbers",
    "application/vnd.apple.keynote",
]

def list_common_files(page_size: int = 200, page_token: str | None = None):
    """
    Return one page of commonly-used document types in Drive.
    Searches My Drive + Shared drives, no trashed.
    """
    svc = drive_service()
    if not svc:
        return ([], None)

    q_types = " or ".join([f"mimeType='{m}'" for m in _COMMON_MIME_LIST])
    q = f"({q_types}) and trashed=false"

    res = svc.files().list(
        pageSize=min(int(page_size or 200), 1000),
        pageToken=page_token,
        q=q,
        fields="nextPageToken, files(id,name,mimeType,size,md5Checksum)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        corpora="user",
        spaces="drive",
    ).execute()
    return (res.get("files", []), res.get("nextPageToken"))


def download_file(file_id: str, out_path: str) -> bool:
    svc = drive_service()
    if not svc: return False
    req = svc.files().get_media(fileId=file_id)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.FileIO(out_path, 'wb') as fh:
        dl = MediaIoBaseDownload(fh, req); done = False
        try:
            while not done: _, done = dl.next_chunk()
            return True
        except Exception:
            try:
                if os.path.exists(out_path): os.remove(out_path)
            except Exception: pass
            return False

def trash_or_delete(file_id: str, mode: str = 'trash') -> bool:
    svc = drive_service()
    if not svc: return False
    try:
        if mode == 'hard': svc.files().delete(fileId=file_id).execute()
        else: svc.files().update(fileId=file_id, body={"trashed": True}).execute()
        return True
    except Exception:
        return False
