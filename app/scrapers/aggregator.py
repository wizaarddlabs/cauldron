"""
Fans a search query out to every registered scraper concurrently and
merges/deduplicates the results by info_hash.
"""
import asyncio
import logging

from app.models import TorrentResult
from app.scrapers.base import Scraper
from app.scrapers.jackett_scraper import JackettScraper

logger = logging.getLogger(__name__)

# Add additional Scraper subclasses here to expand sources.
_SCRAPERS: list[Scraper] = [
    JackettScraper(),
]


async def search_all(query: str, *, imdb_id: str | None = None) -> list[TorrentResult]:
    tasks = [_safe_search(scraper, query, imdb_id) for scraper in _SCRAPERS]
    results_per_scraper = await asyncio.gather(*tasks)

    merged: dict[str, TorrentResult] = {}
    for results in results_per_scraper:
        for result in results:
            existing = merged.get(result.info_hash)
            if existing is None or (result.seeders or 0) > (existing.seeders or 0):
                merged[result.info_hash] = result

    return sorted(merged.values(), key=lambda r: r.seeders or 0, reverse=True)


async def _safe_search(scraper: Scraper, query: str, imdb_id: str | None) -> list[TorrentResult]:
    try:
        return await scraper.search(query, imdb_id=imdb_id)
    except Exception:
        logger.exception("Scraper %s failed", scraper.name)
        return []
