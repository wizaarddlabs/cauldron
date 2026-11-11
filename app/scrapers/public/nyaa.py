"""Nyaa (HTML scraping), anime-focused."""

import logging
import re
from urllib.parse import quote

from bs4 import BeautifulSoup

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

settings = get_settings()


class NyaaMixin:
    """Adds ``_search_nyaa`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_nyaa(
        self,
        queries: list[str],
    ) -> list[TorrentResult]:

        logger.debug(
            "Starting Nyaa search..."
        )

        results = []

        try:
            async with http_session(
                timeout=self.timeout
            ) as client:

                for query in queries[:3]:

                    try:
                        logger.debug(
                            f"Nyaa searching for: {query}"
                        )

                        url = (
                            "https://nyaa.si/"
                            f"?q={quote(query)}"
                            "&s=seeders&o=desc"
                        )

                        headers = {
                            "User-Agent": "Mozilla/5.0"
                        }

                        resp = await client.get(
                            url,
                            headers=headers,
                        )

                        logger.debug(
                            f"Nyaa response status: "
                            f"{resp.status_code}"
                        )

                        if resp.status_code != 200:
                            continue

                        soup = BeautifulSoup(
                            resp.text,
                            "html.parser",
                        )

                        rows = soup.select(
                            "tbody tr"
                        )

                        logger.debug(
                            f"Nyaa found {len(rows)} rows"
                        )

                        for row in rows[1:]:

                            try:
                                cols = row.select("td")

                                if len(cols) < 4:
                                    continue

                                magnet_link = (
                                    cols[2].select_one(
                                        "a[href^='magnet:']"
                                    )
                                )

                                if not magnet_link:
                                    continue

                                magnet = magnet_link[
                                    "href"
                                ]

                                magnet_match = re.search(
                                    r'magnet:\?xt=urn:btih:'
                                    r'([a-fA-F0-9]{40})',
                                    magnet,
                                )

                                if not magnet_match:
                                    continue

                                info_hash = (
                                    magnet_match
                                    .group(1)
                                    .lower()
                                )

                                title_link = (
                                    cols[1].select_one(
                                        "a"
                                    )
                                )

                                title = (
                                    title_link.text.strip()
                                    if title_link
                                    else ""
                                )

                                seeders = 0
                                leechers = 0

                                try:
                                    seeders = int(
                                        cols[3]
                                        .text
                                        .strip()
                                    )

                                    leechers = int(
                                        cols[4]
                                        .text
                                        .strip()
                                    )

                                except (
                                    ValueError,
                                    AttributeError,
                                ):
                                    pass

                                size_str = (
                                    cols[1]
                                    .text
                                    .strip()
                                )

                                size_match = re.search(
                                    r'\d+\.?\d*\s*[GMK]B',
                                    size_str,
                                    re.IGNORECASE,
                                )

                                size = (
                                    size_match.group(0)
                                    if size_match
                                    else ""
                                )

                                results.append(
                                    TorrentResult(
                                        title=title,
                                        info_hash=info_hash,
                                        magnet=magnet,
                                        size_bytes=self._parse_size(
                                            size
                                        ),
                                        seeders=seeders,
                                        leechers=leechers,
                                        source="nyaa",
                                        indexer="Nyaa",
                                        quality=extract_quality(
                                            title
                                        ),
                                    )
                                )

                            except Exception:

                                logger.debug("Skipping unparseable Nyaa result", exc_info=True)

                                continue

                    except Exception:
                        logger.debug("Skipping unparseable Nyaa result", exc_info=True)
                        continue

        except Exception:

            logger.warning("Nyaa search failed", exc_info=True)

        return results
