import asyncio

import pytest

from app.api import playback_cache
from app.logging_utils import mask_config_id, redact_value


@pytest.fixture(autouse=True)
def _clean_state():
    playback_cache._playback_cache.clear()
    playback_cache._playback_locks.clear()
    yield
    playback_cache._playback_cache.clear()
    playback_cache._playback_locks.clear()


def test_expired_entries_and_idle_locks_are_pruned(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(playback_cache.time, "monotonic", lambda: now[0])

    playback_cache.cache_playback_url("old", "https://old")
    asyncio.run(playback_cache.get_playback_lock("idle"))
    assert "idle" in playback_cache._playback_locks

    now[0] += playback_cache.PLAYBACK_CACHE_TTL + 1
    playback_cache.cache_playback_url("new", "https://new")

    assert "old" not in playback_cache._playback_cache
    assert "new" in playback_cache._playback_cache
    assert "idle" not in playback_cache._playback_locks


def test_cache_is_capped(monkeypatch):
    monkeypatch.setattr(playback_cache, "PLAYBACK_CACHE_MAX_ENTRIES", 3)

    for index in range(5):
        playback_cache.cache_playback_url(f"k{index}", f"https://{index}")

    assert list(playback_cache._playback_cache) == ["k2", "k3", "k4"]


def test_held_locks_are_not_pruned():
    async def scenario():
        lock = await playback_cache.get_playback_lock("busy")
        async with lock:
            playback_cache.prune_playback_state()
            assert playback_cache._playback_locks.get("busy") is lock

    asyncio.run(scenario())


def test_mask_config_id():
    assert mask_config_id("0123456789abcdef") == "012345..."
    assert mask_config_id("abc") == "***"


def test_redact_removes_api_key():
    assert redact_value(ValueError("bad key SECRET"), "SECRET") == "bad key ***"


def test_build_stream_debrid_and_p2p():
    from app.api.stream_format import build_stream
    from app.models import CacheStatus, TorrentResult

    torrent = TorrentResult(
        title="Movie 2024 1080p",
        info_hash="A" * 40,
        magnet="magnet:?xt=urn:btih:" + "A" * 40,
        source="scraper",
        seeders=12,
        size_bytes=2 * 1024**3,
        quality="1080P",
        indexer="TPB",
    )
    cache = {"a" * 40: CacheStatus.CACHED}

    debrid = build_stream(
        torrent,
        cache_status_map=cache,
        has_debrid=True,
        base_url="https://c.example",
        config="cfg",
    )
    assert debrid["url"] == f"https://c.example/cfg/playback/{'a' * 40}"
    assert "⚡ Cached" in debrid["name"]
    assert "Size: 2.00 GB" in debrid["title"]

    p2p = build_stream(
        torrent,
        cache_status_map=cache,
        has_debrid=False,
        base_url="https://c.example",
        config="cfg",
    )
    assert p2p["infoHash"] == "a" * 40
    assert "P2P" in p2p["name"]
    assert "url" not in p2p


def test_build_stream_skips_missing_hash():
    from types import SimpleNamespace

    from app.api.stream_format import build_stream

    assert build_stream(
        SimpleNamespace(info_hash="", title="x"),
        cache_status_map={},
        has_debrid=False,
        base_url="",
        config="c",
    ) is None
