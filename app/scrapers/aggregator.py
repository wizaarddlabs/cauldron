import asyncio
import logging
import time

from app.config import get_settings
from app.debrid.torrin import TorrinClient
from app.models import TorrentResult
from app.ranking.preferences import RankingPreferences
from app.ranking.scorer import rank_results
from app.scrapers.base import Scraper
from app.scrapers.comet import CometScraper
from app.scrapers.mediafusion import MediaFusionScraper
from app.scrapers.prowlarr import ProwlarrScraper
from app.scrapers.public_scraper import PublicScraper
from app.scrapers.title_matching import result_matches_request

logger = logging.getLogger(__name__)
settings = get_settings()


_SCRAPERS: list[Scraper] = [
    PublicScraper(),
    CometScraper(),
    MediaFusionScraper(),
    ProwlarrScraper(),
]


# ---------------------------------------------------------
# SAFE SCRAPER
# ---------------------------------------------------------


async def _safe_search(
    scraper: Scraper,
    query: str,
    imdb_id: str | None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
) -> list[TorrentResult]:
    started_at = time.perf_counter()
    try:
        results = await asyncio.wait_for(
            scraper.search(
                query,
                imdb_id=imdb_id,
                season=season,
                episode=episode,
                media_type=media_type,
            ),
            timeout=settings.scrape_timeout_seconds,
        )

        logger.info(
            "%s returned %d raw results for %r in %.2fs",
            scraper.name,
            len(results),
            query,
            time.perf_counter() - started_at,
        )

        return results

    except TimeoutError:
        logger.warning(
            "Scraper %s timed out after %.2fs for %r",
            scraper.name,
            time.perf_counter() - started_at,
            query,
        )
        return []
    except Exception as exc:
        logger.warning(
            "Scraper %s failed after %.2fs (%s)",
            scraper.name,
            time.perf_counter() - started_at,
            type(exc).__name__,
        )

        return []


async def _safe_torrin_account_search(api_key: str) -> list[TorrentResult]:
    started_at = time.perf_counter()
    try:
        results = await asyncio.wait_for(
            TorrinClient(api_key).search_account(),
            timeout=settings.scrape_timeout_seconds,
        )
        logger.info(
            "Torrin account search returned %d results in %.2fs",
            len(results),
            time.perf_counter() - started_at,
        )
        return results
    except TimeoutError:
        logger.warning(
            "Torrin account search timed out after %.2fs",
            time.perf_counter() - started_at,
        )
    except Exception as exc:
        logger.warning(
            "Torrin account search failed after %.2fs (%s)",
            time.perf_counter() - started_at,
            type(exc).__name__,
        )

    return []


# ---------------------------------------------------------
# AGGREGATOR
# ---------------------------------------------------------


async def search_all(
    query: str,
    *,
    imdb_id: str | None = None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
    preferences: RankingPreferences | None = None,
    account_provider: str | None = None,
    account_api_key: str | None = None,
    year: int | None = None,
    aliases: list | None = None,
) -> list[TorrentResult]:

    logger.info(
        "=== AGGREGATOR SEARCH === query=%r imdb=%r type=%r S%sE%s",
        query,
        imdb_id,
        media_type,
        season,
        episode,
    )

    # -----------------------------------------------------
    # SEARCH ALL SCRAPERS CONCURRENTLY
    # -----------------------------------------------------

    tasks = [
        _safe_search(
            scraper,
            query,
            imdb_id,
            season,
            episode,
            media_type,
        )
        for scraper in _SCRAPERS
    ]

    if account_provider == "torrin" and account_api_key:
        tasks.append(_safe_torrin_account_search(account_api_key))

    results_per_scraper = await asyncio.gather(
        *tasks
    )

    raw_count = sum(
        len(results)
        for results in results_per_scraper
    )

    # -----------------------------------------------------
    # TITLE / EPISODE FILTER
    # -----------------------------------------------------

    filtered_results: list[TorrentResult] = []

    for scraper_results in results_per_scraper:
        for result in scraper_results:
            if result_matches_request(
                result,
                query,
                media_type,
                season,
                episode,
                aliases=aliases,
                year=year,
            ):
                filtered_results.append(result)

    logger.info(
        "TITLE FILTER: %d -> %d results",
        raw_count,
        len(filtered_results),
    )

    # -----------------------------------------------------
    # DEDUPLICATION
    # -----------------------------------------------------

    merged: dict[str, TorrentResult] = {}

    for result in filtered_results:
        info_hash = str(
            getattr(
                result,
                "info_hash",
                "",
            )
            or ""
        ).lower()

        # Results without an info hash cannot safely be
        # deduplicated, but should still be retained.
        if not info_hash:
            unique_key = (
                f"nohash:"
                f"{getattr(result, 'title', '')}:"
                f"{getattr(result, 'magnet', '')}"
            )
        else:
            unique_key = info_hash

        existing = merged.get(unique_key)

        if existing is None:
            merged[unique_key] = result
            continue

        # A completed Torrin account job is directly playable for this user.
        # Keep that representation if the same hash also came from a public
        # indexer, so its account availability is not lost.
        if (
            getattr(result, "source", "") == "torrin-account"
            or getattr(existing, "source", "") == "torrin-account"
        ):
            if getattr(result, "source", "") == "torrin-account":
                merged[unique_key] = result
            continue

        # Keep the result with more seeders.
        if (
            (getattr(result, "seeders", None) or 0)
            > (getattr(existing, "seeders", None) or 0)
        ):
            merged[unique_key] = result

    results = list(
        merged.values()
    )

    logger.info(
        "AFTER DEDUPLICATION: %d results",
        len(results),
    )

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

    if preferences:
        results = rank_results(
            results,
            preferences,
        )
    else:
        results = sorted(
            results,
            key=lambda r: getattr(
                r,
                "seeders",
                0,
            )
            or 0,
            reverse=True,
        )

    logger.info(
        "FINAL AGGREGATOR RESULTS: %d",
        len(results),
    )

    return results
