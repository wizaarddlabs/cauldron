import base64

import httpx
import pytest

from app import http_client
from app.scrapers import prowlarr as prowlarr_module
from app.scrapers.prowlarr import ProwlarrScraper, hash_from_magnet

HEX = "a" * 40
HEX_B = "b" * 40
HEX_C = "c" * 40
HEX_D = "d" * 40
B32_OF_D = base64.b32encode(bytes.fromhex(HEX_D)).decode()


def _release(**overrides):
    release = {
        "title": "Inception 2010 1080p BluRay",
        "size": 2_000_000_000,
        "seeders": 42,
        "leechers": 3,
        "indexer": "EXT",
        "protocol": "torrent",
    }
    release.update(overrides)
    return release


@pytest.fixture
def prowlarr(monkeypatch):
    """A fake Prowlarr; returns the list of requests it saw."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)

        if request.url.path == "/api/v1/search":
            if request.headers.get("X-Api-Key") != "SECRET":
                return httpx.Response(401)
            return httpx.Response(200, json=[
                _release(infoHash=HEX.upper()),
                _release(title="Inception 2010 720p", magnetUrl=f"magnet:?xt=urn:btih:{HEX_B}&dn=x"),
                _release(title="Inception 2010 2160p", magnetUrl=f"magnet:?xt=urn:btih:{B32_OF_D}"),
                _release(title="Inception 2010 x265", downloadUrl="http://prowlarr.test/1/download?link=abc"),
                _release(title="Inception 2010 broken", downloadUrl="http://prowlarr.test/1/download?link=dead"),
                _release(title="Inception 2010 NZB", protocol="usenet", infoHash=HEX_C),
            ])

        if request.url.path == "/1/download":
            if request.url.params.get("link") == "abc":
                return httpx.Response(301, headers={"location": f"magnet:?xt=urn:btih:{HEX_C}"})
            return httpx.Response(200, content=b"not a magnet")

        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(http_client, "_client", client)
    yield seen
    monkeypatch.setattr(http_client, "_client", None)


def _scraper(monkeypatch, url="http://prowlarr.test", key="SECRET", ids=""):
    settings = prowlarr_module.get_settings()
    monkeypatch.setattr(settings, "prowlarr_url", url)
    monkeypatch.setattr(settings, "prowlarr_api_key", key)
    monkeypatch.setattr(settings, "prowlarr_indexer_ids", ids)
    return ProwlarrScraper()


def test_hash_from_magnet():
    assert hash_from_magnet(f"magnet:?xt=urn:btih:{HEX.upper()}") == HEX
    assert hash_from_magnet(f"magnet:?dn=x&xt=urn:btih:{B32_OF_D}") == HEX_D
    assert hash_from_magnet("http://example/x") is None
    assert hash_from_magnet(None) is None


async def test_disabled_without_url_or_key(monkeypatch, prowlarr):
    assert await _scraper(monkeypatch, url="").search("Inception", media_type="movie") == []
    assert await _scraper(monkeypatch, key="").search("Inception", media_type="movie") == []
    assert prowlarr == []


async def test_search_maps_releases(monkeypatch, prowlarr):
    results = await _scraper(monkeypatch).search("Inception", media_type="movie")

    by_hash = {r.info_hash: r for r in results}
    # infoHash, hex magnet, base32 magnet, and a download link that redirects to a magnet.
    assert set(by_hash) == {HEX, HEX_B, HEX_D, HEX_C}
    # Usenet and the dead link are dropped; the C hash comes from the redirect, not the NZB.
    assert by_hash[HEX_C].title == "Inception 2010 x265"
    assert by_hash[HEX].source == "prowlarr"
    assert by_hash[HEX].indexer == "EXT"
    assert (by_hash[HEX].seeders, by_hash[HEX].leechers, by_hash[HEX].size_bytes) == (42, 3, 2_000_000_000)
    assert by_hash[HEX_B].magnet.startswith("magnet:?xt=urn:btih:")


async def test_request_uses_header_key_and_movie_category(monkeypatch, prowlarr):
    await _scraper(monkeypatch, ids="7, 12,x").search("Inception", media_type="movie")

    search = next(r for r in prowlarr if r.url.path == "/api/v1/search")
    assert "SECRET" not in str(search.url)
    assert search.headers["X-Api-Key"] == "SECRET"
    assert search.url.params.get_list("categories") == ["2000"]
    assert search.url.params.get_list("indexerIds") == ["7", "12"]
    assert search.url.params["query"] == "Inception"


async def test_series_searches_episode_and_season(monkeypatch, prowlarr):
    await _scraper(monkeypatch).search("Severance", season="2", episode="3", media_type="series")

    queries = sorted(r.url.params["query"] for r in prowlarr if r.url.path == "/api/v1/search")
    assert queries == ["Severance S02", "Severance S02E03"]
    assert all(
        r.url.params.get_list("categories") == ["5000"]
        for r in prowlarr if r.url.path == "/api/v1/search"
    )


async def test_prowlarr_errors_return_no_results(monkeypatch, prowlarr):
    results = await _scraper(monkeypatch, key="WRONG").search("Inception", media_type="movie")

    assert results == []


async def test_results_reach_stremio_through_the_aggregator(monkeypatch, prowlarr):
    from app.scrapers import aggregator

    scraper = _scraper(monkeypatch)
    monkeypatch.setattr(aggregator, "_SCRAPERS", [scraper])

    results = await aggregator.search_all("Inception", media_type="movie", year=2010)

    assert {r.info_hash for r in results} == {HEX, HEX_B, HEX_C, HEX_D}
