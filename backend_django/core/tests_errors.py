"""Phase 23 — humanize_error mapping tests."""
import errno
import json

import httplib2
import pytest
from django.db import OperationalError
from googleapiclient.errors import HttpError

from core.errors import humanize_error


def _http_error(status, reason="", message=""):
    body = {"error": {"code": status, "message": message, "errors": [{"reason": reason}]}}
    return HttpError(httplib2.Response({"status": str(status)}), json.dumps(body).encode())


class OperationalErrorLike(Exception):
    """Stands in for psycopg.OperationalError etc. (matched by class name)."""


OperationalErrorLike.__name__ = "OperationalError"


class ConnectionErrorLike(Exception):
    """Stands in for redis.exceptions.ConnectionError (matched by class name)."""


ConnectionErrorLike.__name__ = "ConnectionError"


@pytest.mark.unit
@pytest.mark.parametrize("exc, code", [
    (_http_error(401, "authError", "Invalid Credentials"), "http_401"),
    (_http_error(403, "forbidden", "The caller does not have permission"), "http_403"),
    (_http_error(403, "insufficientPermissions", "Insufficient Permission"), "http_403_scope"),
    (_http_error(403, "accessNotConfigured", "Gmail API has not been used in project 1 before"), "api_not_enabled"),
    (_http_error(404, "notFound", "Requested entity was not found."), "http_404"),
    (_http_error(429, "rateLimitExceeded", "Too many requests"), "http_429"),
    (_http_error(403, "userRateLimitExceeded", "User rate limit exceeded"), "http_429"),
    (_http_error(403, "exportSizeLimitExceeded", "This file is too large to be exported"), "export_size_limit"),
    (_http_error(400, "failedPrecondition", "Precondition check failed."), "failed_precondition"),
    (Exception("invalid_grant: Token has been expired or revoked."), "invalid_grant"),
    (ConnectionError("Connection refused"), "connection_error"),
    (ConnectionErrorLike("Error 111 connecting to redis:6379"), "connection_error"),
    (OperationalError("could not connect to server"), "db_unavailable"),
    (OperationalErrorLike("connection refused"), "db_unavailable"),
    (OSError(errno.ENOSPC, "No space left on device"), "disk_full"),
    (PermissionError(errno.EACCES, "Permission denied", "/media/imported"), "media_permission"),
])
def test_exception_mapping(exc, code):
    result = humanize_error(exc)
    assert result["code"] == code
    assert result["title"] and result["hint"]


@pytest.mark.unit
@pytest.mark.parametrize("text, code", [
    ('<HttpError 401 when requesting https://x returned "Invalid Credentials">', "http_401"),
    ('<HttpError 404 when requesting https://x returned "Not Found">', "http_404"),
    ('<HttpError 429 when requesting https://x returned "rateLimitExceeded">', "http_429"),
    ("invalid_grant: Bad Request", "invalid_grant"),
    ("OSError: [Errno 28] No space left on device", "disk_full"),
    ('HttpError 400 ... "failedPrecondition"', "failed_precondition"),
])
def test_text_mapping(text, code):
    assert humanize_error(text)["code"] == code


@pytest.mark.unit
def test_unknown_exception_keeps_raw_text_in_code():
    result = humanize_error(ValueError("weird thing 42"))
    assert result["code"] == "weird thing 42"
    assert result["title"] == "Something went wrong"
    assert result["hint"]


@pytest.mark.unit
@pytest.mark.parametrize("value, code", [("totally unknown", "totally unknown"), ("", ""), (None, "")])
def test_unknown_text_fallback(value, code):
    result = humanize_error(value)
    assert result["code"] == code
    assert set(result) == {"title", "hint", "code"}
