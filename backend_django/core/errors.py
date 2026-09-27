"""Human-readable error mapper (Phase 23).

Pure function: ``humanize_error(exc_or_text)`` turns an exception (or an error
string, e.g. one stored on a RunLog) into ``{"title", "hint", "code"}``.

Nothing else calls it yet. Exceptions are recognised by duck typing (an
``.resp.status`` attribute, class names in the MRO) so this module imports no
Django, Google, psycopg or redis packages.
"""
import errno
import re

_HTTP_STATUS_RE = re.compile(r"HttpError\s+(\d{3})|\bHTTP\s+(\d{3})\b|\bstatus[\s:=]+(\d{3})\b", re.I)

_QUOTA_MARKERS = ("ratelimitexceeded", "userratelimitexceeded", "quotaexceeded", "dailylimitexceeded")
_API_DISABLED_MARKERS = ("accessnotconfigured", "has not been used", "api has not been enabled", "is disabled")
_SCOPE_MARKERS = ("insufficientpermissions", "insufficient authentication scopes", "insufficient permission", "scope")


def _result(title, hint, code):
    return {"title": title, "hint": hint, "code": code}


def _http_status(exc):
    for holder in (getattr(exc, "resp", None), exc):
        for attr in ("status", "status_code"):
            value = getattr(holder, attr, None)
            try:
                if value is not None and 100 <= int(value) <= 599:
                    return int(value)
            except (TypeError, ValueError):
                pass
    return None


def _status_from_text(text):
    match = _HTTP_STATUS_RE.search(text)
    if match:
        return int(next(g for g in match.groups() if g))
    return None


def _exception_text(exc):
    parts = [str(exc)]
    content = getattr(exc, "content", None)
    if isinstance(content, bytes):
        content = content.decode("utf-8", "replace")
    if content:
        parts.append(str(content))
    return " ".join(p for p in parts if p)


def _from_text_markers(text, low):
    """Google / OAuth error markers that identify the failure regardless of HTTP status."""
    if "invalid_grant" in low:
        return _result(
            "Google access was revoked or has expired",
            "The saved sign-in token no longer works. Reconnect the Google account.",
            "invalid_grant",
        )
    if "exportsizelimit" in low:
        return _result(
            "File is too large for Google to export",
            "Google refuses to convert this file. Download the original instead of exporting it.",
            "export_size_limit",
        )
    if "failedprecondition" in low:
        return _result(
            "Google rejected the request as out of date",
            "The item is usually already gone or in a different state on Google's side. Re-sync and check again.",
            "failed_precondition",
        )
    if "no space left on device" in low or "errno 28" in low:
        return _disk_full()
    return None


def _from_http_status(status, low):
    if status in (401, 403) and any(m in low for m in _QUOTA_MARKERS):
        return _quota()
    if status == 403 and any(m in low for m in _API_DISABLED_MARKERS):
        return _result(
            "Google API is not enabled",
            "Enable the Gmail / Drive API for this project in Google Cloud Console, wait a few minutes, retry.",
            "api_not_enabled",
        )
    if status in (401, 403) and any(m in low for m in _SCOPE_MARKERS):
        return _result(
            "Google permission (scope) is missing",
            "The token was granted without the required access. Reconnect the account and accept every permission.",
            f"http_{status}_scope",
        )
    if status == 401:
        return _result(
            "Google sign-in expired",
            "The token is missing or no longer valid. Reconnect the Google account.",
            "http_401",
        )
    if status == 403:
        return _result(
            "Google denied access",
            "The token, its permissions (scopes) or the API setting does not allow this. Reconnect and check the API is enabled.",
            "http_403",
        )
    if status == 404:
        return _result(
            "Item not found on Google",
            "It was probably deleted or moved after it was listed. This is usually safe to ignore.",
            "http_404",
        )
    if status == 429:
        return _quota()
    return None


def _quota():
    return _result(
        "Google rate limit or quota reached",
        "Too many requests. The job backs off and retries; if it keeps happening, wait or lower the sync rate.",
        "http_429",
    )


def _disk_full():
    return _result(
        "Disk is full",
        "There is no space left on the storage volume. Free space or point MEDIA_ROOT at a larger disk.",
        "disk_full",
    )


def _from_exception_type(exc):
    """Non-HTTP failures, matched by type: errno, builtin classes and class names in the MRO."""
    mro_names = {cls.__name__ for cls in type(exc).__mro__}
    if isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
        return _disk_full()
    if isinstance(exc, PermissionError):
        return _result(
            "Cannot write to the media folder",
            "The app has no permission on its storage directory. Check ownership and permissions of MEDIA_ROOT.",
            "media_permission",
        )
    if "OperationalError" in mro_names:
        return _result(
            "Database is unreachable",
            "The database refused or dropped the connection. Check the database container / service is running.",
            "db_unavailable",
        )
    if isinstance(exc, ConnectionError) or "ConnectionError" in mro_names:
        return _result(
            "Redis or another service is unreachable",
            "A connection was refused or dropped. Check the redis (and database) containers are running.",
            "connection_error",
        )
    return None


def humanize_error(exc_or_text):
    """Return ``{"title", "hint", "code"}`` for an exception or an error string.

    Unknown input gets a generic title and the raw text as ``code``.
    """
    if isinstance(exc_or_text, BaseException):
        exc = exc_or_text
        text = _exception_text(exc)
        status = _http_status(exc)
        typed = _from_exception_type(exc)
    else:
        text = "" if exc_or_text is None else str(exc_or_text)
        status = _status_from_text(text)
        typed = None

    low = text.lower()
    for found in (
        _from_text_markers(text, low),
        _from_http_status(status, low) if status else None,
        typed,
    ):
        if found:
            return found

    raw = text or (type(exc_or_text).__name__ if isinstance(exc_or_text, BaseException) else "")
    return _result(
        "Something went wrong",
        "No specific advice for this error. The raw message is in the code field; check the logs.",
        raw,
    )
