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


def _get_redis():
    global _redis_client
    if _redis_client is None and settings.redis_url:
        import redis.asyncio as redis

        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    redis_client = _get_redis()
    if redis_client:
        raw = await redis_client.get(key)
        return json.loads(raw) if raw else None

    entry = _memory_store.get(key)
    if not entry:
        return None
    expires_at, raw = entry
    if time.time() > expires_at:
        _memory_store.pop(key, None)
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl_seconds: int) -> None:
    raw = json.dumps(value)
    redis_client = _get_redis()
    if redis_client:
        await redis_client.set(key, raw, ex=ttl_seconds)
        return

    _memory_store[key] = (time.time() + ttl_seconds, raw)
