import logging

import httpx
import pytest

from app import http_client
from app.scrapers import public_scraper
from app.scrapers.public.common import extract_quality, parse_size
from app.scrapers.public_scraper import PublicScraper

TPB_HASH = "A" * 40


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "apibay.org":
        return httpx.Response(
            200,
            json=[
                {
                    "name": "Movie 2024 1080p WEBRip",
                    "info_hash": TPB_HASH,
                    "seeders": "42",
                    "size": "1.5 GB",
                }
            ],
        )

    return httpx.Response(404)


@pytest.fixture
def mocked_http(monkeypatch):
    client = httpx.AsyncClient(transport=httpx.MockTransport(_handler))
    monkeypatch.setattr(http_client, "_client", client)
    monkeypatch.setattr(public_scraper.settings, "bitsearch_enabled", False)
    monkeypatch.setattr(public_scraper.settings, "zilean_enabled", False)
    yield
    monkeypatch.setattr(http_client, "_client", None)


async def test_search_merges_sources_without_errors(mocked_http, caplog):
    caplog.set_level(logging.DEBUG, logger="app.scrapers")

    results = await PublicScraper().search("Movie", media_type="movie")

    assert [r.info_hash for r in results] == [TPB_HASH.lower()]
    assert results[0].seeders == 42
    assert results[0].quality == "1080P"
    assert results[0].size_bytes == int(1.5 * 1024**3)

    # Every source must fail "cleanly" on a 404 rather than by raising
    # (e.g. a NameError swallowed by a broad except).
    assert not [
        r for r in caplog.records
        if "search failed" in r.getMessage() or "unparseable" in r.getMessage()
    ]


@pytest.mark.parametrize(
    "method, args",
    [
        ("_search_1337x", (["q"],)),
        ("_search_nyaa", (["q"],)),
        ("_search_yts", (["q"], "tt1")),
        ("_search_eztv", (["q"], "tt1")),
        ("_search_bitsearch", ("q",)),
        ("_search_zilean", ("tt1",)),
    ],
)
async def test_each_source_handles_http_errors(mocked_http, caplog, method, args):
    caplog.set_level(logging.DEBUG, logger="app.scrapers")

    results = await getattr(PublicScraper(), method)(*args)

    assert results == []
    assert not [r for r in caplog.records if r.exc_info and not isinstance(
        r.exc_info[1], httpx.HTTPError | ValueError
    )]


def test_parse_size_and_quality_helpers():
    assert parse_size("700 MB") == 700 * 1024**2
    assert parse_size("garbage") is None
    assert PublicScraper._parse_size("2 GB") == 2 * 1024**3
    assert extract_quality("Show S01E01 2160p") == "2160P"
    assert extract_quality("") is None
