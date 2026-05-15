import io
import json
import os
from typing import Optional

from decouple import config
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .utils import get_fernet

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

CLIENT_SECRETS = config("GOOGLE_CLIENT_SECRETS", default="secrets/google_client.json")
TOKEN_FILE_ENC = config("GOOGLE_TOKEN_FILE", default="secrets/google_token.json")
MIME_ALLOWLIST = [
    m.strip()
    for m in config("GOOGLE_MIME_ALLOWLIST", default="image/jpeg").split(",")
    if m.strip()
]


def _load_creds() -> Optional[Credentials]:
    if not os.path.exists(TOKEN_FILE_ENC):
        return None
    try:
        with open(TOKEN_FILE_ENC) as f:
            data = json.load(f)
        token_json = get_fernet().decrypt(data["payload"].encode()).decode()
        return Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except Exception:
        return None


def _save_creds(creds: Credentials) -> None:
    os.makedirs(os.path.dirname(TOKEN_FILE_ENC), exist_ok=True)
    wrapped = {"payload": get_fernet().encrypt(creds.to_json().encode()).decode()}
    with open(TOKEN_FILE_ENC, "w") as f:
        json.dump(wrapped, f, indent=2)


def start_oauth_local() -> str:
    """
    Headless OAuth for Desktop App (installed) client type.

    On a server with no browser:
      1. Run: make auth
      2. Open the printed URL in any browser.
      3. Approve access — Google redirects to http://localhost:<port>/?code=...
         The page shows ERR_EMPTY_RESPONSE — that is expected.
      4. Copy the FULL URL from the browser address bar and paste it back.
    """
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    if not os.path.exists(CLIENT_SECRETS):
        return "Missing client secrets at secrets/google_client.json"

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)

    # redirect_uri MUST exactly match the registered URI in google_client.json.
    # Desktop/installed clients register "http://localhost" (no port).
    flow.redirect_uri = "http://localhost"
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    print("\n" + "=" * 60)
    print("Step 1: Open this URL in your browser:\n")
    print(auth_url)
    print("\nStep 2: After approving, Google redirects to http://localhost/?code=...")
    print("        That page will fail to load — that is expected.")
    print("        Copy the FULL URL from the browser address bar and paste below.")
    print("=" * 60)

    redirect_response = input("\nPaste the full redirect URL here: ").strip()

    if "code=" not in redirect_response:
        return "ERROR: No authorization code found in the URL."

    flow.fetch_token(authorization_response=redirect_response)
    _save_creds(flow.credentials)
    return "OAuth completed and token saved."


def drive_service():
    creds = _load_creds()
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
    return build("drive", "v3", credentials=creds)


def list_media_files(page_size: int = 200, page_token: str | None = None):
    """Return one page of media files (images/videos) from Drive."""
    svc = drive_service()
    if not svc:
        return ([], None)

    q_parts = [
        "(mimeType contains 'image/' or mimeType contains 'video/')",
        "trashed = false",
        "(mimeType = 'application/vnd.google-apps.shortcut' and "
        "(shortcutDetails.targetMimeType contains 'image/' or "
        " shortcutDetails.targetMimeType contains 'video/'))",
    ]
    q = f"({q_parts[0]}) and {q_parts[1]} or ({q_parts[2]})"

    res = svc.files().list(
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
        corpora="user",
        spaces="drive",
    ).execute()
    return (res.get("files", []), res.get("nextPageToken"))


def photos_service():
    """Google Photos Library API client."""
    creds = _load_creds()
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds)
    return build("photoslibrary", "v1", credentials=creds, static_discovery=False)


def list_photos_items(page_size: int = 200, page_token: str | None = None):
    """Return mediaItems from Google Photos Library."""
    svc = photos_service()
    if not svc:
        return ([], None)
    res = svc.mediaItems().list(
        pageSize=min(int(page_size or 200), 1000),
        pageToken=page_token,
    ).execute()
    return (res.get("mediaItems", []) or [], res.get("nextPageToken"))


_COMMON_MIME_LIST = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain",
    "text/csv",
    "application/zip",
    "application/x-7z-compressed",
    "application/x-rar-compressed",
    "application/vnd.apple.pages",
    "application/vnd.apple.numbers",
    "application/vnd.apple.keynote",
]


def list_common_files(page_size: int = 200, page_token: str | None = None):
    """Return one page of document-type files from Drive."""
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
    if not svc:
        return False
    req = svc.files().get_media(fileId=file_id)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with io.FileIO(out_path, "wb") as fh:
        dl = MediaIoBaseDownload(fh, req)
        done = False
        try:
            while not done:
                _, done = dl.next_chunk()
            return True
        except Exception:
            try:
                if os.path.exists(out_path):
                    os.remove(out_path)
            except Exception:
                pass
            return False


def trash_or_delete(file_id: str, mode: str = "trash") -> bool:
    svc = drive_service()
    if not svc:
        return False
    try:
        if mode == "hard":
            svc.files().delete(fileId=file_id).execute()
        else:
            svc.files().update(fileId=file_id, body={"trashed": True}).execute()
        return True
    except Exception:
        return False
