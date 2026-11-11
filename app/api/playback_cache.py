"""
In-memory cache of resolved debrid playback URLs, plus per-key locks so
concurrent Stremio requests for the same torrent create only one transfer.
"""

import asyncio
import time

# =========================================================
# PLAYBACK CACHE
# =========================================================
#
# Stremio can request the same playback URL multiple times.
# Without caching, every GET would:
#
#   1. Create a new Premiumize transfer
#   2. Poll Premiumize
#   3. Return another redirect
#
# Keep resolved playback URLs temporarily in memory.
#
# This is intentionally short because debrid playback URLs
# can expire.
# =========================================================

PLAYBACK_CACHE_TTL = 300  # 5 minutes

# Upper bound on remembered playback URLs; oldest entries are evicted first.
PLAYBACK_CACHE_MAX_ENTRIES = 2000

_playback_cache: dict[str, tuple[str, float]] = {}

_playback_locks: dict[str, asyncio.Lock] = {}

_playback_cache_lock = asyncio.Lock()


def prune_playback_state() -> None:
    """
    Drop expired playback URLs and idle per-key locks.

    Without this, every distinct (config, hash) pair ever played would
    stay in memory for the lifetime of the process.
    """

    now = time.monotonic()

    for key in [
        key
        for key, (_, expires_at) in _playback_cache.items()
        if expires_at <= now
    ]:
        _playback_cache.pop(key, None)

    overflow = len(_playback_cache) - PLAYBACK_CACHE_MAX_ENTRIES
    if overflow > 0:
        # Dicts keep insertion order, so the first keys are the oldest.
        for key in list(_playback_cache)[:overflow]:
            _playback_cache.pop(key, None)

    for key in [
        key
        for key, lock in _playback_locks.items()
        if not lock.locked() and key not in _playback_cache
    ]:
        _playback_locks.pop(key, None)


async def get_playback_lock(key: str) -> asyncio.Lock:
    """
    Get a per-playback lock.

    This prevents multiple simultaneous Stremio requests
    from creating multiple transfers for the same torrent.
    """

    async with _playback_cache_lock:
        prune_playback_state()

        lock = _playback_locks.get(key)

        if lock is None:
            lock = asyncio.Lock()
            _playback_locks[key] = lock

        return lock


def get_cached_playback_url(key: str) -> str | None:
    """
    Return a cached playback URL if it is still valid.
    """

    cached = _playback_cache.get(key)

    if not cached:
        return None

    playback_url, expires_at = cached

    if time.monotonic() >= expires_at:
        _playback_cache.pop(key, None)
        return None

    return playback_url


def cache_playback_url(
    key: str,
    playback_url: str,
) -> None:
    """
    Cache a resolved playback URL.
    """

    _playback_cache.pop(key, None)
    _playback_cache[key] = (
        playback_url,
        time.monotonic() + PLAYBACK_CACHE_TTL,
    )
    prune_playback_state()
