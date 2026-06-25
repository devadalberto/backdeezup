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
    "https://mail.google.com/",
]

CLIENT_SECRETS = config("GOOGLE_CLIENT_SECRETS", default="secrets/google_client.json")
TOKEN_FILE_ENC = config("GOOGLE_TOKEN_FILE", default="secrets/google_token.json")
MIME_ALLOWLIST = [
    m.strip()
    for m in config("GOOGLE_MIME_ALLOWLIST", default="image/jpeg").split(",")
    if m.strip()
]


def _token_path_for_email(email: str | None = None) -> str:
    """Return per-account token path. Falls back to TOKEN_FILE_ENC for single-account setup."""
    if not email:
        return TOKEN_FILE_ENC
    import hashlib
    h = hashlib.sha256(email.lower().encode()).hexdigest()[:8]
    token_dir = os.path.dirname(TOKEN_FILE_ENC)
    return os.path.join(token_dir, f"google_token_{h}.json")


def _load_creds(email: str | None = None) -> Optional[Credentials]:
    token_path = _token_path_for_email(email)
    if not os.path.exists(token_path):
        return None
    try:
        with open(token_path) as f:
            data = json.load(f)
        token_json = get_fernet().decrypt(data["payload"].encode()).decode()
        return Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    except Exception:
        return None


def _save_creds(creds: Credentials, email: str | None = None) -> None:
    """
    Atomically write the encrypted token file.
    Uses write-to-temp-then-rename to prevent partial writes from corrupting
    the token on concurrent refreshes or power loss mid-write.
    Sets file permissions to 0o600 (owner read/write only).
    """
    import tempfile
    token_path = _token_path_for_email(email)
    token_dir = os.path.dirname(token_path)
    os.makedirs(token_dir, exist_ok=True)
    wrapped = {"payload": get_fernet().encrypt(creds.to_json().encode()).decode()}
    # Write to a sibling temp file, then atomically rename
    fd, tmp_path = tempfile.mkstemp(dir=token_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(wrapped, f, indent=2)
        os.chmod(tmp_path, 0o600)  # owner read/write only — never world-readable
        os.replace(tmp_path, token_path)  # atomic on POSIX
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


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

    # redirect_uri MUST exactly match one of the registered URIs in google_client.json.
    # Reads the first redirect_uri from the client secrets file automatically.
    client_type = list(json.load(open(CLIENT_SECRETS)).keys())[0]
    registered = json.load(open(CLIENT_SECRETS))[client_type].get("redirect_uris", [])
    # Prefer localhost:8844 callback, then 18444, then first available
    preferred = [u for u in registered if "8844" in u or "18444" in u]
    flow.redirect_uri = preferred[0] if preferred else registered[0]

    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

    print("\n" + "=" * 60)
    print("Step 1: Open this URL in your browser:\n")
    print(auth_url)
    print(f"\nStep 2: After approving, Google redirects to:\n  {flow.redirect_uri}?code=...")
    print("        The page may fail to load — that is expected.")
    print("        Copy the FULL URL from the browser address bar and paste below.")
    print("=" * 60)

    redirect_response = input("\nPaste the full redirect URL here: ").strip()

    if "code=" not in redirect_response:
        return "ERROR: No authorization code found in the URL."

    flow.fetch_token(authorization_response=redirect_response)
    _save_creds(flow.credentials, email=None)
    return "OAuth completed and token saved."


def drive_service(email: str | None = None):
    creds = _load_creds(email)
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds, email)
    return build("drive", "v3", credentials=creds)


def list_media_files(page_size: int = 200, page_token: str | None = None):
    """Return one page of media files (images/videos) from Drive."""
    svc = drive_service()
    if not svc:
        return ([], None)

    q = "(mimeType contains 'image/' or mimeType contains 'video/') and trashed = false"

    res = svc.files().list(
        pageSize=min(int(page_size or 200), 1000),
        pageToken=page_token,
        q=q,
        fields="nextPageToken, files(id,name,mimeType,size,md5Checksum)",
        spaces="drive",
    ).execute()
    return (res.get("files", []), res.get("nextPageToken"))


def photos_service(email: str | None = None):
    """Google Photos Library API client."""
    creds = _load_creds(email)
    if not creds:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_creds(creds, email)
    return build("photoslibrary", "v1", credentials=creds, static_discovery=False)


def list_photos_items(page_size: int = 200, page_token: str | None = None):
    """Return mediaItems from Google Photos Library."""
    svc = photos_service()
    if not svc:
        return ([], None)
    res = svc.mediaItems().list(
        pageSize=min(int(page_size or 100), 100),  # Photos API max is 100
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

GOOGLE_EXPORT_MAP = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}

_GOOGLE_NATIVE_MIMES = list(GOOGLE_EXPORT_MAP.keys())


def list_common_files(page_size: int = 200, page_token: str | None = None):
    """Return one page of document-type files from Drive."""
    svc = drive_service()
    if not svc:
        return ([], None)

    all_doc_mimes = _COMMON_MIME_LIST + _GOOGLE_NATIVE_MIMES
    q_types = " or ".join([f"mimeType='{m}'" for m in all_doc_mimes])
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


def _cleanup_partial(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def download_file(file_id: str, out_path: str) -> bool:
    import time
    from googleapiclient.errors import HttpError
    svc = drive_service()
    if not svc:
        return False
    for attempt in range(4):
        try:
            req = svc.files().get_media(fileId=file_id)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with io.FileIO(out_path, "wb") as fh:
                dl = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = dl.next_chunk()
            return True
        except HttpError as e:
            _cleanup_partial(out_path)
            if e.resp.status in (429, 500, 503):
                time.sleep(2 ** attempt)
                continue
            return False
        except Exception:
            _cleanup_partial(out_path)
            return False
    return False


def download_or_export_file(file_id: str, mime_type: str, out_path: str) -> bool:
    """Download a file, or export it if it's a Google native format (Docs/Sheets/Slides)."""
    import time
    from googleapiclient.errors import HttpError

    if mime_type not in GOOGLE_EXPORT_MAP:
        return download_file(file_id, out_path)

    export_mime, _ = GOOGLE_EXPORT_MAP[mime_type]
    svc = drive_service()
    if not svc:
        return False

    for attempt in range(4):
        try:
            req = svc.files().export_media(fileId=file_id, mimeType=export_mime)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with io.FileIO(out_path, "wb") as fh:
                dl = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = dl.next_chunk()
            return True
        except HttpError as e:
            _cleanup_partial(out_path)
            if e.resp.status in (429, 500, 503):
                time.sleep(2 ** attempt)
                continue
            if e.resp.status == 403 and "exportSizeLimit" in str(e):
                # Fall back to CSV for spreadsheets that exceed export size limit
                if mime_type == "application/vnd.google-apps.spreadsheet":
                    csv_path = os.path.splitext(out_path)[0] + ".csv"
                    try:
                        req2 = svc.files().export_media(fileId=file_id, mimeType="text/csv")
                        with io.FileIO(csv_path, "wb") as fh2:
                            dl2 = MediaIoBaseDownload(fh2, req2)
                            done = False
                            while not done:
                                _, done = dl2.next_chunk()
                        return True
                    except Exception:
                        _cleanup_partial(csv_path)
            return False
        except Exception:
            _cleanup_partial(out_path)
            return False
    return False


def list_drive_files(page_size: int = 200, page_token: str | None = None, media_only: bool = True):
    """Unified Drive file lister — media_only=True for images/videos, False for documents."""
    if media_only:
        return list_media_files(page_size=page_size, page_token=page_token)
    else:
        return list_common_files(page_size=page_size, page_token=page_token)


def download_photos_item(media_item_id: str, out_path: str) -> bool:
    """Download a Google Photos item via its baseUrl (NOT Drive files().get_media())."""
    import requests
    svc = photos_service()
    if not svc:
        return False
    try:
        item = svc.mediaItems().get(mediaItemId=media_item_id).execute()
        base_url = item.get("baseUrl")
        if not base_url:
            return False
        mime = item.get("mimeType", "")
        suffix = "=dv" if mime.startswith("video/") else "=d"
        resp = requests.get(base_url + suffix, stream=True, timeout=120)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        return True
    except Exception:
        try:
            if os.path.exists(out_path):
                os.remove(out_path)
        except OSError:
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
