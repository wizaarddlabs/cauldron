"""
Jackett scraper.

Jackett is a self-hosted service that proxies Torznab-compatible search
requests out to whatever indexers you personally add and configure in its
web UI.

Cauldron talks only to your own Jackett instance.
"""

import re
from urllib.parse import quote
from xml.etree import ElementTree

import httpx

from app.config import get_settings
from app.models import TorrentResult
from app.scrapers.base import Scraper


settings = get_settings()

_HASH_RE = re.compile(r"btih:([a-fA-F0-9]{40})")
_TORZNAB_NS = "{http://torznab.com/schemas/2015/feed}"


class JackettScraper(Scraper):
    name = "jackett"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        indexers: str | None = None,
    ):
        self.base_url = (base_url or settings.jackett_url or "").rstrip("/")
        self.api_key = api_key or settings.jackett_api_key
        self.indexers = indexers or settings.jackett_indexers

    async def search(
        self,
        query: str,
        *,
        imdb_id: str | None = None,
    ) -> list[TorrentResult]:

        if not self.base_url or not self.api_key:
            return []

        endpoint = (
            f"{self.base_url}/api/v2.0/indexers/"
            f"{self.indexers}/results/torznab/api"
        )

        params = {
            "apikey": self.api_key,
            "t": "search",
            "q": query,
        }

        # Add IMDb support when available
        if imdb_id:
            params["imdbid"] = imdb_id

        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout_seconds
        ) as client:

            resp = await client.get(
                endpoint,
                params=params,
            )

            resp.raise_for_status()
            xml_text = resp.text

        return self._parse_torznab(xml_text)[
            : settings.max_results_per_scraper
        ]

    def _parse_torznab(
        self,
        xml_text: str,
    ) -> list[TorrentResult]:

        results: list[TorrentResult] = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return results

        for item in root.iterfind(".//item"):

            title_el = item.find("title")
            link_el = item.find("link")

            if title_el is None or title_el.text is None:
                continue

            title = title_el.text.strip()

            magnet = None
            info_hash = None
            size_bytes = None
            seeders = None
            indexer = None

            # Torznab attributes
            for attr in item.iterfind(f"{_TORZNAB_NS}attr"):

                name = attr.get("name")
                value = attr.get("value")

                if name == "magneturl" and value:
                    magnet = value

                elif name == "infohash" and value:
                    info_hash = value.lower()

                elif name == "seeders" and value:
                    try:
                        seeders = int(value)
                    except ValueError:
                        pass

                elif name == "size" and value:
                    try:
                        size_bytes = int(value)
                    except ValueError:
                        pass

            # Jackett custom indexer field
            indexer_el = item.find("jackettindexer")
            if indexer_el is not None:
                indexer = indexer_el.text

            # Fallback magnet
            if (
                not magnet
                and link_el is not None
                and link_el.text
                and link_el.text.startswith("magnet:")
            ):
                magnet = link_el.text

            # Extract hash from magnet
            if not info_hash and magnet:

                match = _HASH_RE.search(magnet)

                if match:
                    info_hash = match.group(1).lower()

            # Debrid requires hash
            if not info_hash:
                continue

            if not magnet:
                magnet = (
                    f"magnet:?xt=urn:btih:{info_hash}"
                    f"&dn={quote(title)}"
                )

            results.append(
                TorrentResult(
                    title=title,
                    info_hash=info_hash,
                    magnet=magnet,
                    size_bytes=size_bytes,
                    seeders=seeders,
                    source=self.name,
                    indexer=indexer,
                    quality=_extract_quality(title),
                )
            )

        return results


def _extract_quality(title: str) -> str | None:

    qualities = (
        "2160p",
        "4K",
        "1080p",
        "720p",
        "480p",
        "CAM",
        "HDCAM",
        "TS",
    )

    title_lower = title.lower()

    for quality in qualities:
        if quality.lower() in title_lower:
            return quality

    return None
