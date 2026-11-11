"""
Public torrent site scrapers - no external services required.

Sources (one module each under app/scrapers/public/):

- Zilean (optional, self-hosted DMM hash lists)
- Bitsearch (API)
- The Pirate Bay (via apibay.org API)
- 1337x (web scraping)
- YTS (API)
- Nyaa (web scraping) - Anime-focused
- EZTV (API) - TV-focused
"""

import asyncio
import logging

from app.config import get_settings
from app.models import TorrentResult
from app.scrapers.base import Scraper
from app.scrapers.public.bitsearch import BitsearchMixin
from app.scrapers.public.common import extract_quality, parse_size
from app.scrapers.public.eztv import EztvMixin
from app.scrapers.public.nyaa import NyaaMixin
from app.scrapers.public.tpb import PirateBayMixin
from app.scrapers.public.x1337 import X1337Mixin
from app.scrapers.public.yts import YtsMixin
from app.scrapers.public.zilean import ZileanMixin

logger = logging.getLogger(__name__)

settings = get_settings()

# Backwards-compatible aliases for the helpers that used to live here.
_extract_quality = extract_quality


class PublicScraper(
    ZileanMixin,
    BitsearchMixin,
    PirateBayMixin,
    X1337Mixin,
    YtsMixin,
    NyaaMixin,
    EztvMixin,
    Scraper,
):
    """
    Aggregates results from multiple public torrent sources.
    Falls back between sources if one fails.
    """

    name = "public"

    def __init__(self):
        self.timeout = settings.scrape_timeout_seconds
        self._bitsearch_cache: dict[
            str,
            tuple[float, list[TorrentResult]]
        ] = {}

    async def search(
        self,
        query: str,
        *,
        imdb_id: str | None = None,
        season: str | None = None,
        episode: str | None = None,
        media_type: str | None = None,
    ) -> list[TorrentResult]:
        """
        Search across all public sources and merge results.
        """

        all_results = []

        queries = self._build_queries(
            query,
            season,
            episode,
            media_type,
        )

        tasks = [
            self._search_tpb(queries, imdb_id),
            self._search_1337x(queries),
            self._search_nyaa(queries),
        ]

        if settings.bitsearch_enabled:
            tasks.append(
                self._search_bitsearch(queries[0])
            )

        if settings.zilean_enabled and imdb_id:
            tasks.append(
                self._search_zilean(
                    imdb_id,
                    season,
                    episode,
                )
            )

        if media_type == "movie":
            tasks.append(
                self._search_yts(
                    queries,
                    imdb_id,
                )
            )
        elif media_type == "series":
            tasks.append(
                self._search_eztv(
                    queries,
                    imdb_id,
                )
            )

        results_lists = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        for results in results_lists:
            if isinstance(results, Exception):
                continue

            if isinstance(results, list):
                all_results.extend(results)

        seen_hashes = set()
        unique_results = []

        for result in all_results:
            if result.info_hash not in seen_hashes:
                seen_hashes.add(result.info_hash)
                unique_results.append(result)

        unique_results.sort(
            key=lambda r: r.seeders or 0,
            reverse=True,
        )

        return unique_results

    def _build_queries(
        self,
        query: str,
        season: str | None = None,
        episode: str | None = None,
        media_type: str | None = None,
    ) -> list[str]:
        """Build multiple query variations for better results."""

        queries = [query]

        if media_type == "series" and season and episode:
            try:
                s = int(season)
                e = int(episode)

                queries.extend([
                    f"{query} S{s:02d}E{e:02d}",
                    f"{query} Season {s} Episode {e}",
                    f"{query} {s}x{e}",
                ])

            except ValueError:
                pass

        return list(dict.fromkeys(queries))

    @staticmethod
    def _parse_size(
        size_str: str,
    ) -> int | None:
        """Convert a human-readable torrent size to bytes."""
        return parse_size(size_str)
