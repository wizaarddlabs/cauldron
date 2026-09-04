import pytest

from app.cache import store


@pytest.mark.asyncio
async def test_disable_cache_bypasses_memory_store(monkeypatch):
    store._memory_store.clear()
    monkeypatch.setattr(store.settings, "disable_cache", True)

    await store.cache_set("key", {"value": 1}, 60)

    assert await store.cache_get("key") is None
    assert store._memory_store == {}