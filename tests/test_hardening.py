import sqlite3

import pytest
from fastapi import HTTPException

from app import config_store
from app.api import routes, stremio
from app.cache import store
from app.models import AvailabilityRequest, DebridProvider
from app.ranking.preferences import RankingPreferences
from app.security import require_admin_api_key


def test_config_ids_have_high_entropy_and_load_legacy_ids(monkeypatch, tmp_path):
    monkeypatch.setattr(config_store, "DB", tmp_path / "cauldron.db")

    config_id = config_store.save_config({"api_key": "secret"})

    assert len(config_id) == 32
    assert config_store.load_config(config_id) == {"api_key": "secret"}
    with sqlite3.connect(config_store.DB) as connection:
        stored_data = connection.execute(
            "SELECT data FROM configs WHERE id=?",
            (config_id,),
        ).fetchone()[0]
    assert stored_data.startswith("fernet:")
    assert "secret" not in stored_data

    with sqlite3.connect(config_store.DB) as connection:
        connection.execute(
            "INSERT INTO configs VALUES (?, ?, ?)",
            ("legacy01", "2024-01-01T00:00:00+00:00", '{"legacy": true}'),
        )

    assert config_store.load_config("legacy01") == {"legacy": True}


def test_admin_writes_are_disabled_without_configured_key(monkeypatch):
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: type("Settings", (), {"admin_api_key": None})(),
    )

    with pytest.raises(HTTPException) as error:
        require_admin_api_key("anything")

    assert error.value.status_code == 503


def test_admin_key_is_checked_without_timing_sensitive_comparison(monkeypatch):
    monkeypatch.setattr(
        "app.security.get_settings",
        lambda: type("Settings", (), {"admin_api_key": "secret"})(),
    )

    require_admin_api_key("secret")

    with pytest.raises(HTTPException) as error:
        require_admin_api_key("wrong")

    assert error.value.status_code == 403


def test_filter_failure_returns_error_instead_of_unfiltered_results(monkeypatch):
    def fail_apply(self, results):
        raise ValueError("bad filter config")

    monkeypatch.setattr(
        "app.filtering.pipeline.FilterPipeline.apply",
        fail_apply,
    )

    with pytest.raises(HTTPException) as error:
        stremio._apply_configured_filters(["unfiltered"], {})

    assert error.value.status_code == 500
    assert error.value.detail == "Failed to apply configured filters"


@pytest.mark.asyncio
async def test_cache_backend_status_reports_redis_failure(monkeypatch):
    class FailedRedis:
        async def ping(self):
            raise ConnectionError("unavailable")

    monkeypatch.setattr(store.settings, "disable_cache", False)
    monkeypatch.setattr(store, "_get_redis", lambda: FailedRedis())

    assert await store.get_cache_backend_status() == "unavailable"


def test_availability_request_keeps_credentials_in_json_payload():
    request = AvailabilityRequest(
        q="Example",
        provider=DebridProvider.ALLDEBRID,
        api_key="secret",
    )

    assert request.model_dump() == {
        "q": "Example",
        "provider": DebridProvider.ALLDEBRID,
        "api_key": "secret",
        "imdb_id": None,
        "season": None,
        "episode": None,
        "media_type": None,
    }


@pytest.mark.asyncio
async def test_search_cache_refreshes_when_ranking_preferences_change(monkeypatch):
    cache = {}
    cache_keys = []
    searched_preferences = []
    current_preferences = [RankingPreferences()]

    async def fake_cache_get(key):
        cache_keys.append(key)
        return cache.get(key)

    async def fake_cache_set(key, value, ttl_seconds):
        cache[key] = value

    async def fake_search_all(query, **kwargs):
        searched_preferences.append(kwargs["preferences"])
        return []

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)
    monkeypatch.setattr(routes, "cache_set", fake_cache_set)
    monkeypatch.setattr(
        routes,
        "load_preferences",
        lambda: current_preferences[0],
    )
    monkeypatch.setattr(routes, "search_all", fake_search_all)

    await routes.search(q="Example")
    current_preferences[0] = RankingPreferences(seeder_weight=2.0)
    await routes.search(q="Example")
    await routes.search(q="Example")

    assert len(searched_preferences) == 2
    assert cache_keys[0] != cache_keys[1]
    assert cache_keys[1] == cache_keys[2]
