"""Bitsearch JSON API."""

import logging
import re
import time
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

settings = get_settings()


class BitsearchMixin:
    """Adds ``_search_bitsearch`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_bitsearch(
        self,
        query: str,
    ) -> list[TorrentResult]:
        """Search Bitsearch's API."""

        cached = self._bitsearch_cache.get(query)

        now = time.monotonic()

        if (
            cached
            and now - cached[0]
            < settings.bitsearch_cache_ttl_seconds
        ):
            return cached[1]

        headers = (
            {
                "x-api-key": settings.bitsearch_api_key
            }
            if settings.bitsearch_api_key
            else {}
        )

        params = {
            "q": query,
            "limit": min(
                settings.max_results_per_scraper,
                100,
            ),
            "sort": "seeders",
            "order": "desc",
        }

        try:
            async with http_session(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:

                response = await client.get(
                    f"{settings.bitsearch_api_base}/search",
                    params=params,
                    headers=headers,
                )

                response.raise_for_status()

            payload = response.json()

            if not payload.get("success"):
                return []

            results = []

            for item in payload.get("results", []):

                info_hash = str(
                    item.get("infohash", "")
                ).lower()

                title = item.get("title", "")

                if (
                    not re.fullmatch(
                        r"[a-f0-9]{40}",
                        info_hash,
                    )
                    or not isinstance(title, str)
                    or not title
                ):
                    continue

                try:
                    seeders = int(
                        item.get("seeders") or 0
                    )

                    leechers = int(
                        item.get("leechers") or 0
                    )

                    size_bytes = (
                        int(item["size"])
                        if item.get("size") is not None
                        else None
                    )

                except (TypeError, ValueError):
                    continue

                results.append(
                    TorrentResult(
                        title=title,
                        info_hash=info_hash,
                        magnet=(
                            f"magnet:?xt=urn:btih:"
                            f"{info_hash}&dn={quote(title)}"
                        ),
                        size_bytes=size_bytes,
                        seeders=seeders,
                        leechers=leechers,
                        source="bitsearch",
                        indexer="Bitsearch",
                        quality=extract_quality(title),
                    )
                )

            self._bitsearch_cache[query] = (
                now,
                results,
            )

            return results

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                f"Bitsearch search failed: {exc}"
            )

            return []
