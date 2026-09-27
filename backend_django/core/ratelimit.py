"""Redis-backed concurrency + rate-limit knobs for Google API downloads
(Phase 43).

Both knobs are soft, best-effort throttles, not hard guarantees:
- MAX_CONCURRENT_DOWNLOADS defaults to 2 -- the worker's own effective
  concurrency today (docker-compose.yml: `celery worker -c 2`). Set to 0 to
  disable (today's actual behavior, since nothing enforces this today).
- GOOGLE_API_MAX_RPS defaults to 0 (disabled) -- there is no RPS cap today.

If Redis is unreachable, every function here fails OPEN (never blocks a
download), matching the existing dedup lock in
google_gmail_backup.tasks._acquire_lock. This is independent of, and does not
replace, the exponential backoff on 429/5xx already in Phases 10-11.
"""
import time
from contextlib import contextmanager

from decouple import config
from django.core.cache import cache

MAX_CONCURRENT_DOWNLOADS = config("MAX_CONCURRENT_DOWNLOADS", cast=int, default=2)
GOOGLE_API_MAX_RPS = config("GOOGLE_API_MAX_RPS", cast=int, default=0)

_SEMAPHORE_KEY = "downloads:inflight"
_SEMAPHORE_TTL = 300  # safety valve if a worker is killed mid-download
_RATE_WINDOW_TTL = 2


def _incr(key, timeout=None):
    """cache.incr() raises ValueError if the key doesn't exist yet -- create
    it (starting at 0) and retry, same as a Redis SETNX-then-INCR."""
    try:
        return cache.incr(key)
    except ValueError:
        cache.add(key, 0, timeout=timeout)
        return cache.incr(key)


def _try_acquire_slot(limit):
    count = _incr(_SEMAPHORE_KEY, timeout=_SEMAPHORE_TTL)
    if count > limit:
        cache.decr(_SEMAPHORE_KEY)
        return False
    return True


def wait_for_download_slot(timeout=300):
    """Block until a download slot is free, or give up after timeout and
    proceed anyway (never hang a worker over a soft limit).

    Returns True only if a slot was actually acquired (i.e. must be released);
    False means proceed without one (disabled, gave up, or Redis is down), in
    which case the caller must NOT call release_download_slot() -- there is
    nothing to release, and doing so would drift the counter negative.
    """
    if MAX_CONCURRENT_DOWNLOADS <= 0:
        return False
    deadline = time.time() + timeout
    try:
        while not _try_acquire_slot(MAX_CONCURRENT_DOWNLOADS):
            if time.time() > deadline:
                return False
            time.sleep(0.2)
        return True
    except Exception:
        return False  # Redis unreachable -- fail open


def release_download_slot():
    try:
        cache.decr(_SEMAPHORE_KEY)
    except Exception:
        pass


def wait_for_rate_limit():
    """Block until under GOOGLE_API_MAX_RPS for the current 1-second window."""
    if GOOGLE_API_MAX_RPS <= 0:
        return
    try:
        while True:
            key = f"ratelimit:google_api:{int(time.time())}"
            if _incr(key, timeout=_RATE_WINDOW_TTL) <= GOOGLE_API_MAX_RPS:
                return
            time.sleep(0.05)
    except Exception:
        return  # Redis unreachable -- fail open


@contextmanager
def download_slot():
    """Pace to GOOGLE_API_MAX_RPS, then hold a MAX_CONCURRENT_DOWNLOADS slot
    for the duration of one download. Releases the slot on exit, but only if
    one was actually acquired (see wait_for_download_slot)."""
    wait_for_rate_limit()
    acquired = wait_for_download_slot()
    try:
        yield
    finally:
        if acquired:
            release_download_slot()
