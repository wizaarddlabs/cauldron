import asyncio
import re

import pytest
from fastapi.testclient import TestClient

import app.config_store as config_store
from app.api import debrid_accounts as da
from app.api import stremio
from app.api.debrid_accounts import DebridAccount
from app.main import app
from app.models import CacheStatus, TorrentResult

C, N, U = CacheStatus.CACHED, CacheStatus.NOT_CACHED, CacheStatus.UNKNOWN
HASH_A = "a" * 40
HASH_B = "b" * 40


# ---------------------------------------------------------------- unit


def test_accounts_from_config_keeps_order_and_skips_bad_entries():
    cfg = {
        "providers": [
            {"provider": "torbox", "api_key": "tb"},
            {"provider": "realdebrid", "api_key": ""},  # no key
            {"provider": "evil", "api_key": "x"},  # unknown
            {"provider": "torbox", "api_key": "dup"},  # duplicate
            "junk",
            {"provider": "RealDebrid", "api_key": " rd "},
        ]
    }

    assert da.accounts_from_config(cfg) == [("torbox", "tb"), ("realdebrid", "rd")]
    assert da.accounts_from_config({"provider": "torbox"}) is None


def test_combine_cache_status():
    combined = da.combine_cache_status(
        {"rd": {HASH_A: N, HASH_B: N}, "tb": {HASH_A: C}},
        [HASH_A, HASH_B, "c" * 40],
    )

    assert combined == {HASH_A: C, HASH_B: N, "c" * 40: U}


def test_best_mode_prefers_highest_priority_cached_provider():
    rd, tb = DebridAccount("realdebrid", "k1"), DebridAccount("torbox", "k2")
    maps = {"realdebrid": {HASH_A: N, HASH_B: C}, "torbox": {HASH_A: C, HASH_B: C}}

    assert da.accounts_for_torrent(HASH_A, [rd, tb], maps) == [tb]
    assert da.accounts_for_torrent(HASH_B, [rd, tb], maps) == [rd]
    # Cached nowhere: first provider.
    assert da.accounts_for_torrent("c" * 40, [rd, tb], maps) == [rd]
    assert da.accounts_for_torrent(HASH_A, [rd, tb], maps, "all") == [rd, tb]
    assert da.accounts_for_torrent(HASH_A, [], maps) == []


class FakeClient:
    def __init__(self, statuses=None, delay=0.0, error=None):
        self.statuses = statuses or {}
        self.delay = delay
        self.error = error

    async def check_cache(self, hashes):
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return {h: self.statuses.get(h, N) for h in hashes}


def test_check_all_caches_tolerates_slow_and_failing_providers():
    accounts = [
        DebridAccount("realdebrid", "k1", FakeClient({HASH_A: C})),
        DebridAccount("torbox", "SECRET", FakeClient(error=RuntimeError("bad SECRET"))),
        DebridAccount("alldebrid", "k3", FakeClient(delay=1)),
    ]

    maps = asyncio.run(da.check_all_caches(accounts, [HASH_A], timeout=0.2))

    assert maps == {"realdebrid": {HASH_A: C}, "torbox": {}, "alldebrid": {}}


# ---------------------------------------------------------------- setup form


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "DB", tmp_path / "cauldron.db")
    return TestClient(app)


def _config(html):
    config_id = re.search(r"/([0-9a-f]{32})/manifest\.json", html).group(1)
    return config_id, config_store.load_config(config_id)


def test_form_saves_several_providers_in_priority_order(client):
    response = client.post(
        "/generate",
        data={
            "provider": ["realdebrid", "torbox"],
            "api_key": ["rd", "tb"],
            "stream_mode": "all",
        },
    )

    assert response.status_code == 200
    _, cfg = _config(response.text)
    assert cfg["providers"] == [
        {"provider": "realdebrid", "api_key": "rd"},
        {"provider": "torbox", "api_key": "tb"},
    ]
    assert cfg["stream_mode"] == "all"
    # Single-provider fields mirror the first account for older versions.
    assert (cfg["provider"], cfg["api_key"]) == ("realdebrid", "rd")
    assert "Real-Debrid and TorBox" in response.text


def test_form_rejects_duplicate_provider(client):
    response = client.post(
        "/generate",
        data={"provider": ["torbox", "torbox"], "api_key": ["a", "b"]},
    )

    assert response.status_code == 400
    assert "TorBox is listed more than once" in response.text


def test_form_rejects_backup_provider_without_key_and_keeps_rows(client):
    response = client.post(
        "/generate",
        data={"provider": ["realdebrid", "alldebrid"], "api_key": ["rd", ""]},
    )

    assert response.status_code == 400
    assert "Enter your AllDebrid API key" in response.text
    assert re.search(r'id="provider_1"[^>]*>.*?<option value="realdebrid" selected>', response.text, re.S)
    assert re.search(r'id="provider_2"[^>]*>.*?<option value="alldebrid" selected>', response.text, re.S)
    assert 'value="rd"' not in response.text  # keys are never echoed back


def test_invalid_stream_mode_falls_back_to_best(client):
    response = client.post(
        "/generate",
        data={"provider": ["torbox"], "api_key": ["k"], "stream_mode": "weird"},
    )

    _, cfg = _config(response.text)
    assert cfg["stream_mode"] == "best"


# ---------------------------------------------------------------- /stream


class StreamFakeClient:
    def __init__(self, cached):
        self.cached = set(cached)

    async def check_cache(self, hashes):
        return {h: (C if h in self.cached else N) for h in hashes}


@pytest.fixture
def stream_env(monkeypatch):
    async def fake_media(type_, id_):
        return {"type": type_, "imdb_id": "tt1", "title": "Movie", "year": 2024,
                "aliases": [], "season": None, "episode": None}

    async def fake_search(*args, **kwargs):
        return [
            TorrentResult(title=f"Movie 2024 1080p {h[0]}", info_hash=h,
                          magnet=f"magnet:?xt=urn:btih:{h}", source="scraper", seeders=5)
            for h in (HASH_A, HASH_B)
        ]

    # Real-Debrid has B cached, TorBox has A cached.
    caches = {"realdebrid": {HASH_B}, "torbox": {HASH_A}}
    monkeypatch.setattr(stremio, "resolve_media", fake_media)
    monkeypatch.setattr(stremio, "search_all", fake_search)
    monkeypatch.setattr(
        stremio, "get_debrid_client",
        lambda provider, key: StreamFakeClient(caches[provider.value]),
    )

    def run(cfg):
        monkeypatch.setattr(stremio, "load_config", lambda config_id: cfg)
        response = TestClient(app).get(f"/{'0' * 32}/stream/movie/tt1.json")
        assert response.status_code == 200
        return response.json()["streams"]

    return run


TWO = [{"provider": "realdebrid", "api_key": "rd"}, {"provider": "torbox", "api_key": "tb"}]


def _routes(streams):
    return sorted(
        (s["url"].rsplit("/", 2)[-2], s["url"].rsplit("/", 1)[-1][0], "Cached" in s["name"])
        for s in streams
    )


def test_stream_best_mode_routes_each_torrent_to_its_cached_provider(stream_env):
    streams = stream_env({"providers": TWO})

    # One stream per torrent, each through the provider that has it cached.
    assert _routes(streams) == [("realdebrid", "b", True), ("torbox", "a", True)]
    assert all(("Real-Debrid" in s["name"]) or ("TorBox" in s["name"]) for s in streams)


def test_stream_all_mode_lists_every_provider(stream_env):
    streams = stream_env({"providers": TWO, "stream_mode": "all"})

    assert _routes(streams) == [
        ("realdebrid", "a", False), ("realdebrid", "b", True),
        ("torbox", "a", True), ("torbox", "b", False),
    ]


def test_stream_all_mode_with_cached_only_drops_uncached_providers(stream_env):
    streams = stream_env({"providers": TWO, "stream_mode": "all", "cached_only": True})

    assert _routes(streams) == [("realdebrid", "b", True), ("torbox", "a", True)]


def test_single_provider_config_keeps_plain_names(stream_env):
    streams = stream_env({"provider": "torbox", "api_key": "tb"})

    assert len(streams) == 2
    assert all("/playback/torbox/" in s["url"] for s in streams)
    assert not any("TorBox" in s["name"] for s in streams)


def test_p2p_config_has_no_debrid_streams(stream_env):
    streams = stream_env({"provider": "p2p", "providers": []})

    assert all("infoHash" in s and "url" not in s for s in streams)


# ---------------------------------------------------------------- /playback


@pytest.fixture
def playback_client(monkeypatch):
    monkeypatch.setattr(stremio, "load_config", lambda config_id: {"providers": TWO})
    return TestClient(app)


def test_playback_for_configured_provider(playback_client):
    response = playback_client.head(f"/{'0' * 32}/playback/torbox/{HASH_A}")

    assert response.status_code == 200


def test_playback_rejects_provider_not_in_config(playback_client):
    response = playback_client.head(f"/{'0' * 32}/playback/premiumize/{HASH_A}")

    assert response.status_code == 404


def test_legacy_playback_url_uses_first_provider(monkeypatch, playback_client):
    used = []

    class Client:
        async def add_magnet(self, magnet):
            return "t1"

        async def get_playback_link(self, torrent_id):
            return type("R", (), {"playback_url": "https://cdn.example/f.mkv", "file_name": "f"})()

    def factory(provider, key):
        used.append((provider.value, key))
        return Client()

    monkeypatch.setattr(stremio, "get_debrid_client", factory)

    response = playback_client.get(f"/{'0' * 32}/playback/{HASH_A}", follow_redirects=False)

    assert response.status_code == 302
    assert used == [("realdebrid", "rd")]
