"""Browser-based OAuth (Phase 28).

Reuses the exact client secrets, scopes and token storage as the CLI flow
(``start_oauth_local`` in google_media_backup/services_google.py) -- only the
transport differs: a session-stored ``state`` instead of copy/paste. The
existing ``make auth`` flow is untouched; ``handle_callback`` only takes over
when the session holds a matching, unexpired state.
"""
import os
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from google_auth_oauthlib.flow import InstalledAppFlow

from core.errors import humanize_error
from google_media_backup.services_google import (
    CLIENT_SECRETS,
    SCOPES,
    _load_creds,
    _save_creds,
    _token_path_for_email,
)

SESSION_STATE_KEY = "oauth_state"
SESSION_REDIRECT_KEY = "oauth_redirect_uri"
SESSION_STARTED_KEY = "oauth_started_at"
SESSION_RETURN_KEY = "oauth_return_to"
STATE_TTL = timedelta(minutes=10)

SCOPE_REASONS = {
    "https://www.googleapis.com/auth/drive.readonly": "List and read Drive files to find media to back up.",
    "https://www.googleapis.com/auth/drive": "Trash Drive files once they are safely backed up and verified.",
    "https://www.googleapis.com/auth/gmail.readonly": "List and read Gmail messages to back them up.",
    "https://www.googleapis.com/auth/gmail.modify": "Apply labels and trash messages that match your cleanup rules.",
    "https://mail.google.com/": "Permanently empty Gmail trash once a backup is verified (required by Google for this action).",
}


def scope_list():
    return [{"scope": s, "reason": SCOPE_REASONS.get(s, "")} for s in SCOPES]


def _build_flow(redirect_uri):
    if not os.path.exists(CLIENT_SECRETS):
        raise FileNotFoundError(f"Missing client secrets at {CLIENT_SECRETS}")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


def start(request, return_to="dashboard_connect"):
    """Build the Google auth URL, stash state in the session, return the URL to redirect to.

    ``return_to`` is a URL name the callback redirects to afterward (see
    config/urls.py's ``oauth_callback``) -- Phase 28's dashboard connect page
    by default, or Phase 30's wizard connect step when it calls this.
    """
    redirect_uri = request.build_absolute_uri(reverse("oauth_callback"))
    flow = _build_flow(redirect_uri)
    auth_url, state = flow.authorization_url(prompt="consent", access_type="offline")
    request.session[SESSION_STATE_KEY] = state
    request.session[SESSION_REDIRECT_KEY] = redirect_uri
    request.session[SESSION_STARTED_KEY] = timezone.now().isoformat()
    request.session[SESSION_RETURN_KEY] = return_to
    return auth_url


def _clear_session(request):
    for key in (SESSION_STATE_KEY, SESSION_REDIRECT_KEY, SESSION_STARTED_KEY):
        request.session.pop(key, None)


def pop_return_to(request):
    """The url name ``start()`` recorded to redirect back to; defaults to Phase 28's page."""
    return request.session.pop(SESSION_RETURN_KEY, "dashboard_connect")


def is_our_callback(request):
    """True when this callback belongs to a browser flow we started (session has a
    matching, unexpired state) -- false means it's the CLI's own redirect, which the
    caller must leave untouched."""
    state = request.session.get(SESSION_STATE_KEY)
    started = request.session.get(SESSION_STARTED_KEY)
    if not state or state != request.GET.get("state"):
        return False
    try:
        age = timezone.now() - timezone.datetime.fromisoformat(started)
    except (TypeError, ValueError):
        return False
    return age <= STATE_TTL


def handle_callback(request):
    """Complete a browser-started flow. Returns ``(ok, message)``; always clears the session state."""
    redirect_uri = request.session.get(SESSION_REDIRECT_KEY)
    _clear_session(request)
    if request.GET.get("error"):
        info = humanize_error(request.GET["error"])
        return False, f"{info['title']} -- {info['hint']}"
    try:
        flow = _build_flow(redirect_uri)
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        _save_creds(flow.credentials, email=None)
        return True, "Google account connected."
    except Exception as exc:
        info = humanize_error(exc)
        return False, f"{info['title']} -- {info['hint']}"


def disconnect():
    """Delete the stored token. Never touches backed-up data."""
    path = _token_path_for_email(None)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def status():
    """Connection status for the connect page: same checks as core.health.check_oauth,
    plus the scopes actually on the saved token."""
    from core.health import check_oauth

    check_status, detail = check_oauth()
    creds = _load_creds(None)
    return {
        "status": check_status,
        "detail": detail,
        "scopes": list(getattr(creds, "scopes", None) or []) if creds else [],
    }
