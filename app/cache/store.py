"""
Small async cache abstraction. Uses Redis if REDIS_URL is configured,
otherwise falls back to an in-process TTL dict (fine for local/dev use,
but won't share state across multiple worker processes).
"""
import json
import time
from typing import Any, Optional

from app.config import get_settings

settings = get_settings()

_memory_store: dict[str, tuple[float, str]] = {}
_redis_client = None
_cache_stats = {"hits": 0, "misses": 0}


def _get_redis():
    global _redis_client
    if settings.disable_cache:
        return None
    if _redis_client is None and settings.redis_url:
        import redis.asyncio as redis

        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    if settings.disable_cache:
        return None

    redis_client = _get_redis()
    if redis_client:
        raw = await redis_client.get(key)
        if raw is not None:
            _cache_stats["hits"] += 1
        else:
            _cache_stats["misses"] += 1
        return json.loads(raw) if raw else None

    entry = _memory_store.get(key)
    if not entry:
        _cache_stats["misses"] += 1
        return None
    expires_at, raw = entry
    if time.time() > expires_at:
        _memory_store.pop(key, None)
        _cache_stats["misses"] += 1
        return None
    _cache_stats["hits"] += 1
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    if settings.disable_cache:
        return

    raw = json.dumps(value)
    redis_client = _get_redis()
    if redis_client:
        await redis_client.set(key, raw, ex=ttl_seconds)
        return

    _memory_store[key] = (time.time() + ttl_seconds, raw)


def get_cache_stats() -> dict:
    """Return cache hit/miss statistics."""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = (_cache_stats["hits"] / total * 100) if total > 0 else 0
    return {
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate_percent": round(hit_rate, 2),
        "total_requests": total
    }
