import asyncio

import pytest
from fastapi import HTTPException

from app.api import routes
from app.models import (
    AvailabilityRequest,
    DebridProvider,
    ResolveRequest,
    TorrentResult,
)
from app.scrapers import aggregator


def _torrent(source: str = "test") -> TorrentResult:
    info_hash = "a" * 40
    return TorrentResult(
        title="Example Movie 1080p",
        info_hash=info_hash,
        magnet=f"magnet:?xt=urn:btih:{info_hash}",
        seeders=10,
        source=source,
    )


@pytest.mark.asyncio
async def test_search_keeps_results_when_scraper_fails_or_times_out(monkeypatch):
    class GoodScraper:
        name = "good"

        async def search(self, *args, **kwargs):
            return [_torrent("good")]

    class FailedScraper:
        name = "failed"

        async def search(self, *args, **kwargs):
            raise RuntimeError("source unavailable")

    class SlowScraper:
        name = "slow"

        async def search(self, *args, **kwargs):
            await asyncio.sleep(1)
            return [_torrent("slow")]

    monkeypatch.setattr(
        aggregator,
        "settings",
        type("Settings", (), {"scrape_timeout_seconds": 0.01})(),
    )
    monkeypatch.setattr(
        aggregator,
        "_SCRAPERS",
        [GoodScraper(), FailedScraper(), SlowScraper()],
    )

    results = await aggregator.search_all("Example Movie")

    assert [result.source for result in results] == ["good"]


@pytest.mark.asyncio
async def test_torrin_account_failure_does_not_discard_scraper_results(
    monkeypatch,
    caplog,
):
    class GoodScraper:
        name = "good"

        async def search(self, *args, **kwargs):
            return [_torrent("good")]

    class FailedTorrin:
        def __init__(self, api_key):
            pass

        async def search_account(self):
            raise RuntimeError("account unavailable")

    monkeypatch.setattr(aggregator, "_SCRAPERS", [GoodScraper()])
    monkeypatch.setattr(aggregator, "TorrinClient", FailedTorrin)

    results = await aggregator.search_all(
        "Example Movie",
        account_provider="torrin",
        account_api_key="secret",
    )

    assert [result.source for result in results] == ["good"]
    assert "secret" not in caplog.text


@pytest.mark.asyncio
async def test_availability_provider_failure_returns_safe_502(monkeypatch, caplog):
    async def fake_search_all(*args, **kwargs):
        return [_torrent()]

    async def empty_cache_get(key):
        return None

    class FailedProvider:
        async def check_cache(self, info_hashes):
            raise RuntimeError("request failed with secret")

    monkeypatch.setattr(routes, "search_all", fake_search_all)
    monkeypatch.setattr(routes, "cache_get", empty_cache_get)
    monkeypatch.setattr(routes, "get_debrid_client", lambda *args: FailedProvider())

    with pytest.raises(HTTPException) as error:
        await routes.availability_post(
            AvailabilityRequest(
                q="Example Movie",
                provider=DebridProvider.TORRIN,
                api_key="secret",
            )
        )

    assert error.value.status_code == 502
    assert error.value.detail == "Debrid provider availability check failed"
    assert "secret" not in error.value.detail
    assert "secret" not in caplog.text


@pytest.mark.asyncio
async def test_resolve_provider_failure_returns_safe_502(monkeypatch, caplog):
    class FailedProvider:
        async def add_magnet(self, magnet):
            raise RuntimeError("request failed with secret")

    monkeypatch.setattr(routes, "get_debrid_client", lambda *args: FailedProvider())

    with pytest.raises(HTTPException) as error:
        await routes.resolve(
            ResolveRequest(
                provider=DebridProvider.TORRIN,
                api_key="secret",
                magnet=f"magnet:?xt=urn:btih:{'a' * 40}",
            )
        )

    assert error.value.status_code == 502
    assert error.value.detail == "Debrid provider resolve failed"
    assert "secret" not in error.value.detail
    assert "secret" not in caplog.text
