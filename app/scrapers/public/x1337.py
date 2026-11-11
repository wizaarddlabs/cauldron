"""1337x (HTML scraping)."""

import logging
import re
from urllib.parse import quote

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

settings = get_settings()


class X1337Mixin:
    """Adds ``_search_1337x`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_1337x(
        self,
        queries: list[str],
    ) -> list[TorrentResult]:

        results = []

        try:
            async with http_session(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
            ) as client:

                for query in queries[:3]:

                    try:
                        url = (
                            "https://www.1337xx.to/search/"
                            f"{quote(query)}/1/"
                        )

                        resp = await client.get(url)

                        if resp.status_code != 200:
                            continue

                        html = resp.text

                        pattern = re.compile(
                            r'<a href="/torrent/(\d+)/([^/]+)/?".*?'
                            r'<span class="seeds">(\d+)</span>.*?'
                            r'<span class="leeches">(\d+)</span>.*?'
                            r'<span class="size">(\d+\.?\d*\s*[GMK]B)</span>',
                            re.DOTALL | re.IGNORECASE,
                        )

                        matches = pattern.findall(html)

                        for match in matches:

                            (
                                torrent_id,
                                slug,
                                seeders,
                                leechers,
                                size,
                            ) = match

                            try:
                                torrent_url = (
                                    "https://www.1337xx.to/torrent/"
                                    f"{torrent_id}/{slug}/"
                                )

                                torrent_resp = await client.get(
                                    torrent_url,
                                    headers={
                                        "User-Agent":
                                            "Mozilla/5.0"
                                    },
                                )

                                if torrent_resp.status_code != 200:
                                    continue

                                magnet_match = re.search(
                                    r'magnet:\?xt=urn:btih:'
                                    r'([a-fA-F0-9]{40})',
                                    torrent_resp.text,
                                )

                                if not magnet_match:
                                    continue

                                info_hash = (
                                    magnet_match
                                    .group(1)
                                    .lower()
                                )

                                magnet = (
                                    "magnet:?xt=urn:btih:"
                                    f"{info_hash}"
                                )

                                results.append(
                                    TorrentResult(
                                        title=slug.replace(
                                            "-",
                                            " ",
                                        ),
                                        info_hash=info_hash,
                                        magnet=magnet,
                                        size_bytes=self._parse_size(
                                            size
                                        ),
                                        seeders=(
                                            int(seeders)
                                            if seeders.isdigit()
                                            else 0
                                        ),
                                        source="1337x",
                                        indexer="1337x",
                                        quality=extract_quality(
                                            slug
                                        ),
                                    )
                                )

                            except Exception:

                                logger.debug("Skipping unparseable 1337x result", exc_info=True)

                                continue

                    except Exception:
                        logger.debug("Skipping unparseable 1337x result", exc_info=True)
                        continue

        except Exception:

            logger.warning("1337x search failed", exc_info=True)

        return results
