"""EZTV API, TV-focused."""

import logging
import re

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult
from app.scrapers.public.common import extract_quality

logger = logging.getLogger(__name__)

settings = get_settings()


class EztvMixin:
    """Adds ``_search_eztv`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_eztv(
        self,
        queries: list[str],
        imdb_id: str | None = None,
    ) -> list[TorrentResult]:

        results = []

        try:
            async with http_session(
                timeout=self.timeout
            ) as client:

                base_url = (
                    "https://eztvx.to/api/get-torrents"
                )

                if imdb_id:

                    try:
                        params = {
                            "imdb_id": imdb_id,
                            "limit": 50,
                        }

                        resp = await client.get(
                            base_url,
                            params=params,
                        )

                        if resp.status_code == 200:

                            data = resp.json()

                            torrents = data.get(
                                "torrents",
                                [],
                            )

                            for torrent in torrents:

                                try:
                                    title = torrent.get(
                                        "title",
                                        "",
                                    )

                                    magnet = torrent.get(
                                        "magnet_url",
                                        "",
                                    )

                                    hash_str = torrent.get(
                                        "hash",
                                        "",
                                    )

                                    size_bytes = torrent.get(
                                        "size_bytes"
                                    )

                                    seeds = torrent.get(
                                        "seeds",
                                        0,
                                    )

                                    peers = torrent.get(
                                        "peers",
                                        0,
                                    )

                                    if (
                                        not magnet
                                        or not hash_str
                                    ):
                                        continue

                                    magnet_match = re.search(
                                        r"magnet:\?xt=urn:btih:"
                                        r"([a-fA-F0-9]{40})",
                                        magnet,
                                    )

                                    if not magnet_match:
                                        continue

                                    info_hash = (
                                        magnet_match
                                        .group(1)
                                        .lower()
                                    )

                                    if isinstance(
                                        size_bytes,
                                        str,
                                    ):
                                        try:
                                            size_bytes = int(
                                                size_bytes
                                            )

                                        except ValueError:
                                            size_bytes = None

                                    results.append(
                                        TorrentResult(
                                            title=title,
                                            info_hash=info_hash,
                                            magnet=magnet,
                                            size_bytes=size_bytes,
                                            seeders=seeds,
                                            leechers=peers,
                                            source="eztv",
                                            indexer="EZTV",
                                            quality=extract_quality(
                                                title
                                            ),
                                        )
                                    )

                                except Exception:

                                    logger.debug("Skipping unparseable EZTV result", exc_info=True)

                                    continue

                    except Exception:

                        logger.warning("EZTV search failed", exc_info=True)

                if not results:

                    for query in queries[:2]:

                        try:
                            params = {
                                "limit": 50
                            }

                            resp = await client.get(
                                base_url,
                                params=params,
                            )

                            if resp.status_code != 200:
                                continue

                            data = resp.json()

                            torrents = data.get(
                                "torrents",
                                [],
                            )

                            for torrent in torrents:

                                try:
                                    title = torrent.get(
                                        "title",
                                        "",
                                    ).lower()

                                    query_lower = (
                                        query.lower()
                                    )

                                    if (
                                        query_lower
                                        not in title
                                    ):
                                        continue

                                    magnet = torrent.get(
                                        "magnet_url",
                                        "",
                                    )

                                    hash_str = torrent.get(
                                        "hash",
                                        "",
                                    )

                                    size_bytes = torrent.get(
                                        "size_bytes"
                                    )

                                    seeds = torrent.get(
                                        "seeds",
                                        0,
                                    )

                                    peers = torrent.get(
                                        "peers",
                                        0,
                                    )

                                    if (
                                        not magnet
                                        or not hash_str
                                    ):
                                        continue

                                    magnet_match = re.search(
                                        r"magnet:\?xt=urn:btih:"
                                        r"([a-fA-F0-9]{40})",
                                        magnet,
                                    )

                                    if not magnet_match:
                                        continue

                                    info_hash = (
                                        magnet_match
                                        .group(1)
                                        .lower()
                                    )

                                    if isinstance(
                                        size_bytes,
                                        str,
                                    ):
                                        try:
                                            size_bytes = int(
                                                size_bytes
                                            )

                                        except ValueError:
                                            size_bytes = None

                                    results.append(
                                        TorrentResult(
                                            title=torrent.get(
                                                "title",
                                                "",
                                            ),
                                            info_hash=info_hash,
                                            magnet=magnet,
                                            size_bytes=size_bytes,
                                            seeders=seeds,
                                            leechers=peers,
                                            source="eztv",
                                            indexer="EZTV",
                                            quality=extract_quality(
                                                torrent.get(
                                                    "title",
                                                    "",
                                                )
                                            ),
                                        )
                                    )

                                except Exception:

                                    logger.debug("Skipping unparseable EZTV result", exc_info=True)

                                    continue

                        except Exception:
                            logger.debug("Skipping unparseable EZTV result", exc_info=True)
                            continue

        except Exception:

            logger.warning("EZTV search failed", exc_info=True)

        return results
