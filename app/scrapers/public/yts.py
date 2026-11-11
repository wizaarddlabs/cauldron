"""YTS movie API."""

import logging

from app.config import get_settings
from app.http_client import http_session
from app.models import TorrentResult

logger = logging.getLogger(__name__)

settings = get_settings()


class YtsMixin:
    """Adds ``_search_yts`` to :class:`PublicScraper`."""

    timeout: float

    async def _search_yts(
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
                    "https://yts.mx/api/v2/"
                    "list_movies.json"
                )

                for query in queries[:3]:

                    try:
                        params = {
                            "query_term": query,
                            "limit": 20,
                        }

                        resp = await client.get(
                            base_url,
                            params=params,
                        )

                        if resp.status_code != 200:
                            continue

                        data = resp.json()

                        if data.get("status") != "ok":
                            continue

                        movies = (
                            data.get("data", {})
                            .get("movies", [])
                        )

                        for movie in movies:

                            torrents = movie.get(
                                "torrents",
                                [],
                            )

                            for torrent in torrents:

                                info_hash = torrent.get(
                                    "hash"
                                )

                                if not info_hash:
                                    continue

                                quality = torrent.get(
                                    "quality",
                                    "",
                                )

                                size = torrent.get(
                                    "size",
                                    "",
                                )

                                seeders = torrent.get(
                                    "seeds",
                                    0,
                                )

                                magnet = (
                                    "magnet:?xt=urn:btih:"
                                    f"{info_hash}"
                                )

                                results.append(
                                    TorrentResult(
                                        title=movie.get(
                                            "title_long",
                                            movie.get(
                                                "title",
                                                "",
                                            ),
                                        ),
                                        info_hash=info_hash.lower(),
                                        magnet=magnet,
                                        size_bytes=self._parse_size(
                                            size
                                        ),
                                        seeders=(
                                            int(seeders)
                                            if seeders
                                            else 0
                                        ),
                                        source="yts",
                                        indexer="YTS",
                                        quality=quality,
                                    )
                                )

                    except Exception:

                        logger.debug("Skipping unparseable YTS result", exc_info=True)

                        continue

        except Exception:

            logger.warning("YTS search failed", exc_info=True)

        return results
