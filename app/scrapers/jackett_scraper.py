"""
Jackett scraper.

Jackett is a self-hosted service that proxies Torznab-compatible search
requests out to whatever indexers you personally add and configure in its
web UI (https://github.com/Jackett/Jackett). This project talks only to
your own Jackett instance -- it never embeds or hardcodes any specific
tracker -- so what you search is entirely up to how you configure Jackett.

This is the same integration pattern used by Comet, MediaFusion, and most
other open-source Stremio-debrid addons.
"""
import re
from urllib.parse import quote

import httpx
from xml.etree import ElementTree

from app.config import get_settings
from app.models import TorrentResult
from app.scrapers.base import Scraper

settings = get_settings()

_HASH_RE = re.compile(r"btih:([a-fA-F0-9]{40})")
_TORZNAB_NS = "{http://torznab.com/schemas/2015/feed}"


class JackettScraper(Scraper):
    name = "jackett"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, indexers: str | None = None):
        self.base_url = (base_url or settings.jackett_url or "").rstrip("/")
        self.api_key = api_key or settings.jackett_api_key
        self.indexers = indexers or settings.jackett_indexers

    async def search(self, query: str, *, imdb_id: str | None = None) -> list[TorrentResult]:
        if not self.base_url or not self.api_key:
            # Not configured -- return no results instead of erroring, so the
            # app still works with whatever other scrapers are enabled.
            return []

        endpoint = f"{self.base_url}/api/v2.0/indexers/{self.indexers}/results/torznab/api"
        params = {
            "apikey": self.api_key,
            "t": "search",
            "q": query,
        }

        async with httpx.AsyncClient(timeout=settings.scrape_timeout_seconds) as client:
            resp = await client.get(endpoint, params=params)
            resp.raise_for_status()
            xml_text = resp.text

        return self._parse_torznab(xml_text)[: settings.max_results_per_scraper]

    def _parse_torznab(self, xml_text: str) -> list[TorrentResult]:
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

            title = title_el.text
            magnet = None
            info_hash = None
            size_bytes = None
            seeders = None

            # magnet / infohash often live in a torznab:attr element
            for attr in item.iterfind(f"{_TORZNAB_NS}attr"):
                name = attr.get("name")
                value = attr.get("value")
                if name == "magneturl" and value:
                    magnet = value
                elif name == "infohash" and value:
                    info_hash = value.lower()
                elif name == "seeders" and value:
                    seeders = int(value)
                elif name == "size" and value:
                    size_bytes = int(value)

            if not magnet and link_el is not None and link_el.text and link_el.text.startswith("magnet:"):
                magnet = link_el.text

            if not info_hash and magnet:
                m = _HASH_RE.search(magnet)
                if m:
                    info_hash = m.group(1).lower()

            if not info_hash:
                continue  # can't resolve via debrid without a hash

            if not magnet:
                magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={quote(title)}"

            results.append(
                TorrentResult(
                    title=title,
                    info_hash=info_hash,
                    magnet=magnet,
                    size_bytes=size_bytes,
                    seeders=seeders,
                    source=self.name,
                    indexer=item.findtext("jackettindexer") or item.findtext(f"{_TORZNAB_NS}indexer"),
                    quality=_extract_quality(title),
                )
            )

        return results


def _extract_quality(title: str) -> str | None:
    for pattern in ("2160p", "4K", "1080p", "720p", "480p", "CAM", "HDCAM", "TS"):
        if pattern.lower() in title.lower():
            return pattern
    return None
