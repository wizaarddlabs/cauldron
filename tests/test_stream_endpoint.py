from fastapi.testclient import TestClient

from app.api import stremio
from app.main import app
from app.models import TorrentResult

CONFIG_ID = "0123456789abcdef0123456789abcdef"
HASH = "b" * 40


def test_stream_endpoint_returns_p2p_streams(monkeypatch):
    async def fake_resolve_media(type_, id_):
        return {
            "type": type_,
            "imdb_id": "tt1",
            "title": "Movie",
            "year": 2024,
            "aliases": [],
            "season": None,
            "episode": None,
        }

    async def fake_search_all(*args, **kwargs):
        return [
            TorrentResult(
                title="Movie 2024 1080p",
                info_hash=HASH,
                magnet=f"magnet:?xt=urn:btih:{HASH}",
                source="scraper",
                seeders=5,
            )
        ]

    monkeypatch.setattr(stremio, "load_config", lambda config_id: {})
    monkeypatch.setattr(stremio, "resolve_media", fake_resolve_media)
    monkeypatch.setattr(stremio, "search_all", fake_search_all)

    response = TestClient(app).get(f"/{CONFIG_ID}/stream/movie/tt1.json")

    assert response.status_code == 200
    streams = response.json()["streams"]
    assert [s["infoHash"] for s in streams] == [HASH]


def test_playback_head_does_not_resolve(monkeypatch):
    monkeypatch.setattr(
        stremio,
        "load_config",
        lambda config_id: {"provider": "realdebrid", "api_key": "k"},
    )

    response = TestClient(app).head(f"/{CONFIG_ID}/playback/{HASH}")

    assert response.status_code == 200
