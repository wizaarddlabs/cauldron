"""Optional self-hosted Zilean DMM hash-list index."""

import logging
import re
from urllib.parse import quote

import httpx

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

settings = get_settings()


class ZileanMixin:
    """Adds ``_search_zilean`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_zilean(
        self,
        imdb_id: str,
        season: str | None = None,
        episode: str | None = None,
    ) -> list[TorrentResult]:
        """Query an optional self-hosted Zilean DMM hash-list index."""

        params = {
            "ImdbId": imdb_id,
        }

        if season:
            params["Season"] = season

        if episode:
            params["Episode"] = episode

        try:
            async with http_session(
                timeout=self.timeout
            ) as client:
                response = await client.get(
                    f"{settings.zilean_url.rstrip('/')}/dmm/filtered",
                    params=params,
                )

                response.raise_for_status()

            payload = response.json()

            items = (
                payload
                if isinstance(payload, list)
                else payload.get("results", [])
            )

            results = []

            for item in items[:settings.zilean_max_results]:
                if not isinstance(item, dict):
                    continue

                info_hash = str(
                    item.get("info_hash", "")
                ).lower()

                title = (
                    item.get("raw_title")
                    or item.get("title")
                    or ""
                )

                if (
                    not re.fullmatch(
                        r"[a-f0-9]{40}",
                        info_hash,
                    )
                    or not isinstance(title, str)
                    or not title
                ):
                    continue

                raw_size = item.get("size")

                try:
                    size_bytes = (
                        int(raw_size)
                        if raw_size is not None
                        else None
                    )

                except (TypeError, ValueError):
                    size_bytes = self._parse_size(
                        str(raw_size)
                    )

                results.append(
                    TorrentResult(
                        title=title,
                        info_hash=info_hash,
                        magnet=(
                            f"magnet:?xt=urn:btih:"
                            f"{info_hash}&dn={quote(title)}"
                        ),
                        size_bytes=size_bytes,
                        seeders=None,
                        leechers=None,
                        source="zilean",
                        indexer="Zilean",
                        quality=(
                            item.get("resolution")
                            or extract_quality(title)
                        ),
                        codec=item.get("codec"),
                    )
                )

            return results

        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                f"Zilean search failed: {exc}"
            )

            return []
