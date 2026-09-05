import httpx
import pytest

from app.debrid import torrin
from app.debrid.torrin import TorrinClient
from app.models import CacheStatus


class FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def get(self, url, headers):
        if url.endswith("/torrents"):
            return httpx.Response(
                200,
                json=[
                    {
                        "filename": "Movie.2025.1080p.mkv",
                        "hash": "A" * 40,
                        "bytes": 123,
                        "status": "downloaded",
                    },
                    {"filename": "invalid", "hash": "bad"},
                ],
                request=httpx.Request("GET", url),
            )

        hashes = url.split("/instantAvailability/", 1)[1].split("/")
        return httpx.Response(
            200,
            json={
                hashes[0]: {"rd": [{"1": {}}]},
                hashes[1]: {},
            },
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_torrin_cache_status_parses_availability(monkeypatch):
    monkeypatch.setattr(torrin.httpx, "AsyncClient", FakeAsyncClient)

    hashes = ["A" * 40, "b" * 40]
    result = await TorrinClient("key").check_cache(hashes)

    assert result == {
        "a" * 40: CacheStatus.CACHED,
        "b" * 40: CacheStatus.NOT_CACHED,
    }


@pytest.mark.asyncio
async def test_torrin_account_search_maps_recent_torrents(monkeypatch):
    monkeypatch.setattr(torrin.httpx, "AsyncClient", FakeAsyncClient)

    results = await TorrinClient("key").search_account()

    assert len(results) == 1
    assert results[0].title == "Movie.2025.1080p.mkv"
    assert results[0].source == "torrin-account"
    assert results[0].size_bytes == 123