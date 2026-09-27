"""Phase 43 -- concurrency + rate-limit knobs. Uses a real (in-memory) Django
cache backend, same as Phase 27's tests, since the semaphore/token-bucket
logic is exactly the incr/decr/add semantics under test -- mocking the cache
would just re-describe the implementation instead of exercising it.
"""
from unittest.mock import patch

import pytest

from core import ratelimit

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "p43"}}


@pytest.fixture(autouse=True)
def local_cache(settings):
    settings.CACHES = LOCMEM
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def no_sleep():
    """Every test below runs instantly -- time.sleep is patched out globally
    so a "blocks until a slot frees" test doesn't actually wait."""
    with patch("time.sleep"):
        yield


@pytest.mark.unit
def test_disabled_concurrency_limit_never_touches_the_counter(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 0)
    assert ratelimit.wait_for_download_slot() is False
    from django.core.cache import cache
    assert cache.get(ratelimit._SEMAPHORE_KEY) is None


@pytest.mark.unit
def test_slots_up_to_the_limit_are_acquired(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 2)
    assert ratelimit.wait_for_download_slot() is True
    assert ratelimit.wait_for_download_slot() is True
    from django.core.cache import cache
    assert cache.get(ratelimit._SEMAPHORE_KEY) == 2


@pytest.mark.unit
def test_slot_beyond_the_limit_gives_up_and_does_not_leak_the_counter(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 1)
    assert ratelimit.wait_for_download_slot() is True  # takes the only slot

    got = ratelimit.wait_for_download_slot(timeout=0)  # gives up immediately
    assert got is False

    from django.core.cache import cache
    assert cache.get(ratelimit._SEMAPHORE_KEY) == 1  # unchanged by the failed attempt


@pytest.mark.unit
def test_release_frees_the_slot_for_the_next_waiter(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 1)
    assert ratelimit.wait_for_download_slot() is True
    ratelimit.release_download_slot()

    from django.core.cache import cache
    assert cache.get(ratelimit._SEMAPHORE_KEY) == 0
    assert ratelimit.wait_for_download_slot() is True


@pytest.mark.unit
def test_download_slot_context_manager_releases_on_success(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 1)
    with ratelimit.download_slot():
        from django.core.cache import cache
        assert cache.get(ratelimit._SEMAPHORE_KEY) == 1
    from django.core.cache import cache
    assert cache.get(ratelimit._SEMAPHORE_KEY) == 0


@pytest.mark.unit
def test_download_slot_context_manager_releases_on_exception(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 1)
    with pytest.raises(RuntimeError):
        with ratelimit.download_slot():
            raise RuntimeError("boom")
    from django.core.cache import cache
    assert cache.get(ratelimit._SEMAPHORE_KEY) == 0


@pytest.mark.unit
def test_download_slot_disabled_never_calls_release(monkeypatch):
    """A caller that never acquired must never decrement -- would drift the
    counter negative for everyone else."""
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 0)
    with patch.object(ratelimit, "release_download_slot") as release:
        with ratelimit.download_slot():
            pass
        release.assert_not_called()


@pytest.mark.unit
def test_timed_out_wait_never_calls_release(monkeypatch):
    """download_slot()'s contract: if wait_for_download_slot() reports it
    never acquired a slot, release_download_slot() must not run -- otherwise
    it drifts the shared counter negative for every other caller. Exercised
    directly (not via a real 300s timeout) to keep this test deterministic
    and fast; the timeout mechanics themselves are covered by
    test_slot_beyond_the_limit_gives_up_and_does_not_leak_the_counter."""
    monkeypatch.setattr(ratelimit, "wait_for_download_slot", lambda timeout=300: False)
    with patch.object(ratelimit, "release_download_slot") as release:
        with ratelimit.download_slot():
            pass
        release.assert_not_called()


@pytest.mark.unit
def test_redis_down_fails_open_and_does_not_raise(monkeypatch):
    monkeypatch.setattr(ratelimit, "MAX_CONCURRENT_DOWNLOADS", 1)
    from django.core.cache import cache
    with patch.object(cache, "incr", side_effect=Exception("connection refused")):
        assert ratelimit.wait_for_download_slot() is False
    with ratelimit.download_slot():
        pass  # must not raise


@pytest.mark.unit
def test_rate_limit_disabled_never_touches_cache(monkeypatch):
    monkeypatch.setattr(ratelimit, "GOOGLE_API_MAX_RPS", 0)
    ratelimit.wait_for_rate_limit()
    from django.core.cache import cache
    import time
    assert cache.get(f"ratelimit:google_api:{int(time.time())}") is None


@pytest.mark.unit
def test_rate_limit_allows_up_to_the_cap_in_one_window(monkeypatch):
    monkeypatch.setattr(ratelimit, "GOOGLE_API_MAX_RPS", 3)
    import time
    window = int(time.time())
    monkeypatch.setattr(time, "time", lambda: window)

    for _ in range(3):
        ratelimit.wait_for_rate_limit()

    from django.core.cache import cache
    assert cache.get(f"ratelimit:google_api:{window}") == 3


@pytest.mark.unit
def test_rate_limit_over_the_cap_blocks_until_the_window_advances(monkeypatch):
    monkeypatch.setattr(ratelimit, "GOOGLE_API_MAX_RPS", 1)
    import time as time_mod
    state = {"window": 100, "sleeps": 0}

    def fake_sleep(seconds):
        state["sleeps"] += 1
        state["window"] = 101  # simulate a second passing on the first retry sleep

    monkeypatch.setattr(time_mod, "time", lambda: state["window"])
    monkeypatch.setattr(time_mod, "sleep", fake_sleep)

    ratelimit.wait_for_rate_limit()  # window 100 -> count 1, at the cap, returns immediately
    ratelimit.wait_for_rate_limit()  # window 100 -> count 2, over cap -> sleeps -> window 101 -> count 1, returns

    from django.core.cache import cache
    assert cache.get("ratelimit:google_api:100") == 2
    assert cache.get("ratelimit:google_api:101") == 1
    assert state["sleeps"] == 1


@pytest.mark.unit
def test_redis_down_rate_limit_fails_open(monkeypatch):
    monkeypatch.setattr(ratelimit, "GOOGLE_API_MAX_RPS", 1)
    from django.core.cache import cache
    with patch.object(cache, "incr", side_effect=Exception("connection refused")):
        ratelimit.wait_for_rate_limit()  # must not raise
