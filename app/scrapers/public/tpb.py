"""The Pirate Bay, via the apibay.org API."""

import logging
from urllib.parse import quote

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

settings = get_settings()


class PirateBayMixin:
    """Adds ``_search_tpb`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_tpb(
        self,
        queries: list[str],
        imdb_id: str | None = None,
    ) -> list[TorrentResult]:

        results = []

        try:
            async with http_session(
                timeout=self.timeout
            ) as client:

                for query in queries[:5]:

                    try:
                        url = (
                            "https://apibay.org/q.php"
                            f"?q={quote(query)}"
                        )

                        resp = await client.get(url)

                        if resp.status_code != 200:
                            continue

                        data = resp.json()

                        if (
                            not isinstance(data, list)
                            or len(data) == 0
                        ):
                            continue

                        for item in data:

                            if not isinstance(item, dict):
                                continue

                            info_hash = item.get(
                                "info_hash"
                            )

                            if not info_hash:
                                continue

                            try:
                                seeders = int(
                                    item.get(
                                        "seeders",
                                        0,
                                    )
                                )

                            except (
                                ValueError,
                                TypeError,
                            ):
                                seeders = 0

                            size_bytes = self._parse_size(
                                item.get("size", "")
                            )

                            title = item.get(
                                "name",
                                "",
                            )

                            magnet = (
                                "magnet:?xt=urn:btih:"
                                f"{info_hash}"
                                f"&dn={quote(title)}"
                            )

                            results.append(
                                TorrentResult(
                                    title=title,
                                    info_hash=info_hash.lower(),
                                    magnet=magnet,
                                    size_bytes=size_bytes,
                                    seeders=seeders,
                                    source="thepiratebay",
                                    indexer="ThePirateBay",
                                    quality=extract_quality(
                                        title
                                    ),
                                )
                            )

                    except Exception:

                        logger.debug("Skipping unparseable TPB result", exc_info=True)

                        continue

        except Exception:

            logger.warning("TPB search failed", exc_info=True)

        return results
