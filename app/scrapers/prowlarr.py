"""
Prowlarr source.

Searches every indexer enabled in a Prowlarr instance (for example EXT /
ext.to, which needs Prowlarr's FlareSolverr proxy to get past Cloudflare)
through Prowlarr's search API:

    GET {PROWLARR_URL}/api/v1/search?query=...&type=search&categories=...
    X-Api-Key: {PROWLARR_API_KEY}

Prowlarr does the site-specific scraping; Cauldron only needs each release's
info hash. Releases that come without one are resolved by following their
download link one hop, since Prowlarr redirects magnet-only indexers to the
magnet URI. Usenet results are ignored.

Disabled unless both PROWLARR_URL and PROWLARR_API_KEY are set.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import re
from urllib.parse import parse_qs, urlparse

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.base import Scraper
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

# Newznab/Torznab top-level categories.
_MOVIE_CATEGORIES = [2000]
_TV_CATEGORIES = [5000]

_HEX_HASH = re.compile(r"^[0-9a-fA-F]{40}$")
_BASE32_HASH = re.compile(r"^[A-Za-z2-7]{32}$")

# At most this many hashless releases are resolved per search, a few at a time,
# so one slow indexer can't hold up the whole search.
_MAX_LINK_LOOKUPS = 15
_LINK_LOOKUP_CONCURRENCY = 5


def hash_from_magnet(magnet: str | None) -> str | None:
    """Lowercase hex BTIH from a magnet URI (hex or base32 form), if any."""

    if not magnet or not magnet.lower().startswith("magnet:"):
        return None

    for xt in parse_qs(urlparse(magnet).query).get("xt", []):
        if not xt.lower().startswith("urn:btih:"):
            continue

        value = xt[len("urn:btih:"):]

        if _HEX_HASH.match(value):
            return value.lower()

        if _BASE32_HASH.match(value):
            return base64.b32decode(value.upper()).hex()

    return None


class ProwlarrScraper(Scraper):
    """Search all (or selected) indexers configured in Prowlarr."""

    name = "prowlarr"

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = (settings.prowlarr_url or "").rstrip("/")
        self.api_key = settings.prowlarr_api_key or ""
        self.timeout = settings.prowlarr_timeout_seconds
        self.max_results = settings.max_results_per_scraper
        self.indexer_ids = [
            part.strip()
            for part in (settings.prowlarr_indexer_ids or "").split(",")
            if part.strip().isdigit()
        ]

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _queries(
        self,
        query: str,
        season: str | None,
        episode: str | None,
        media_type: str | None,
    ) -> list[str]:
        if media_type == "series" and season and episode:
            try:
                s, e = int(season), int(episode)
            except ValueError:
                return [query]
            # The episode itself, plus season packs.
            return [f"{query} S{s:02d}E{e:02d}", f"{query} S{s:02d}"]

        return [query]

    async def search(
        self,
        query: str,
        *,
        imdb_id: str | None = None,
        season: str | None = None,
        episode: str | None = None,
        media_type: str | None = None,
    ) -> list[TorrentResult]:
        if not self.enabled:
            return []

        categories = (
            _TV_CATEGORIES if media_type == "series"
            else _MOVIE_CATEGORIES if media_type == "movie"
            else []
        )

        async with http_session(
            timeout=self.timeout,
            headers={"X-Api-Key": self.api_key, "Accept": "application/json"},
        ) as client:

            async def run(search_query: str) -> list[dict]:
                params: list[tuple[str, str]] = [
                    ("query", search_query),
                    ("type", "search"),
                    ("limit", str(self.max_results)),
                ]
                params += [("categories", str(c)) for c in categories]
                params += [("indexerIds", i) for i in self.indexer_ids]

                try:
                    response = await client.get(
                        f"{self.base_url}/api/v1/search",
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json()
                except Exception as exc:
                    logger.warning("Prowlarr search failed for %r: %s", search_query, exc)
                    return []

                return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []

            # Concurrent: the aggregator gives each source one overall time limit.
            batches = await asyncio.gather(
                *(run(q) for q in self._queries(query, season, episode, media_type))
            )
            releases = [release for batch in batches for release in batch]

            results = await self._to_results(client, releases)

        logger.info("Prowlarr: %d releases -> %d torrents", len(releases), len(results))
        return results

    async def _to_results(self, client, releases: list[dict]) -> list[TorrentResult]:
        results: list[TorrentResult] = []
        unresolved: list[dict] = []

        for release in releases:
            if str(release.get("protocol", "torrent")).lower() != "torrent":
                continue

            info_hash = self._hash_of(release)

            if info_hash:
                results.append(self._result(release, info_hash))
            elif release.get("downloadUrl") or release.get("magnetUrl"):
                unresolved.append(release)

        if unresolved:
            semaphore = asyncio.Semaphore(_LINK_LOOKUP_CONCURRENCY)

            async def resolve(release: dict) -> TorrentResult | None:
                async with semaphore:
                    info_hash = await self._hash_from_link(client, release)
                return self._result(release, info_hash) if info_hash else None

            resolved = await asyncio.gather(
                *(resolve(r) for r in unresolved[:_MAX_LINK_LOOKUPS])
            )
            results.extend(r for r in resolved if r)

            skipped = len(unresolved) - sum(1 for r in resolved if r)
            if skipped:
                logger.debug("Prowlarr: %d releases without a usable info hash", skipped)

        return results

    @staticmethod
    def _hash_of(release: dict) -> str | None:
        info_hash = str(release.get("infoHash") or "").strip()

        if _HEX_HASH.match(info_hash):
            return info_hash.lower()

        return hash_from_magnet(release.get("magnetUrl")) or hash_from_magnet(
            release.get("guid")
        )

    async def _hash_from_link(self, client, release: dict) -> str | None:
        """
        Follow a Prowlarr download link one hop: for magnet-only indexers
        Prowlarr answers with a redirect to the magnet URI.
        """

        url = release.get("magnetUrl") or release.get("downloadUrl")

        if not url or not str(url).lower().startswith("http"):
            return None

        try:
            response = await client.get(url, follow_redirects=False)
        except Exception as exc:
            logger.debug("Prowlarr link lookup failed: %s", exc)
            return None

        if response.is_redirect:
            return hash_from_magnet(response.headers.get("location"))

        return None

    @staticmethod
    def _result(release: dict, info_hash: str) -> TorrentResult:
        title = str(release.get("title") or "")

        def as_int(value):
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None

        return TorrentResult(
            title=title,
            info_hash=info_hash,
            magnet=(
                release.get("magnetUrl")
                if str(release.get("magnetUrl") or "").lower().startswith("magnet:")
                else f"magnet:?xt=urn:btih:{info_hash}"
            ),
            size_bytes=as_int(release.get("size")),
            seeders=as_int(release.get("seeders")),
            leechers=as_int(release.get("leechers")),
            source="prowlarr",
            indexer=str(release.get("indexer") or "Prowlarr"),
            quality=extract_quality(title),
        )
