import asyncio

import pytest

from app.api import stremio


@pytest.fixture(autouse=True)
def _clean_state():
    stremio._playback_cache.clear()
    stremio._playback_locks.clear()
    yield
    stremio._playback_cache.clear()
    stremio._playback_locks.clear()


def test_expired_entries_and_idle_locks_are_pruned(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(stremio.time, "monotonic", lambda: now[0])

    stremio._cache_playback_url("old", "https://old")
    asyncio.run(stremio._get_playback_lock("idle"))
    assert "idle" in stremio._playback_locks

    now[0] += stremio.PLAYBACK_CACHE_TTL + 1
    stremio._cache_playback_url("new", "https://new")

    assert "old" not in stremio._playback_cache
    assert "new" in stremio._playback_cache
    assert "idle" not in stremio._playback_locks


def test_cache_is_capped(monkeypatch):
    monkeypatch.setattr(stremio, "PLAYBACK_CACHE_MAX_ENTRIES", 3)

    for index in range(5):
        stremio._cache_playback_url(f"k{index}", f"https://{index}")

    assert list(stremio._playback_cache) == ["k2", "k3", "k4"]


def test_held_locks_are_not_pruned():
    async def scenario():
        lock = await stremio._get_playback_lock("busy")
        async with lock:
            stremio._prune_playback_state()
            assert stremio._playback_locks.get("busy") is lock

    asyncio.run(scenario())


def test_mask_config_id():
    assert stremio._mask_config_id("0123456789abcdef") == "012345..."
    assert stremio._mask_config_id("abc") == "***"


def test_redact_removes_api_key():
    assert stremio._redact(ValueError("bad key SECRET"), "SECRET") == "bad key ***"
