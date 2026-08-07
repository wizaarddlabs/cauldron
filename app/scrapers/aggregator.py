"""
Fans a search query out to every registered scraper concurrently
and merges/deduplicates torrent results.
"""

import asyncio
import logging

from app.models import TorrentResult
from app.scrapers.base import Scraper
from app.scrapers.public_scraper import PublicScraper

from app.ranking.preferences import RankingPreferences
from app.ranking.scorer import rank_results


logger = logging.getLogger(__name__)


_SCRAPERS: list[Scraper] = [
    PublicScraper(),
]


async def search_all(
    query: str,
    *,
    imdb_id: str | None = None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
    preferences: RankingPreferences | None = None,
) -> list[TorrentResult]:

    tasks = []

    for scraper in _SCRAPERS:

        tasks.append(
            _safe_search(
                scraper,
                query,
                imdb_id,
                season,
                episode,
                media_type
            )
        )


    results_per_scraper = await asyncio.gather(
        *tasks
    )


    merged: dict[str, TorrentResult] = {}


    for results in results_per_scraper:

        for result in results:

            existing = merged.get(
                result.info_hash
            )


            if (
                existing is None
                or (result.seeders or 0)
                > (existing.seeders or 0)
            ):
                merged[result.info_hash] = result


    results = list(
        merged.values()
    )


    if preferences:

        return rank_results(
            results,
            preferences
        )


    return sorted(
        results,
        key=lambda r: r.seeders or 0,
        reverse=True,
    )



async def _safe_search(
    scraper: Scraper,
    query: str,
    imdb_id: str | None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
) -> list[TorrentResult]:

    try:

        return await scraper.search(
            query,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            media_type=media_type,
        )


    except Exception:

        logger.exception(
            "Scraper %s failed",
            scraper.name,
        )

        return []
