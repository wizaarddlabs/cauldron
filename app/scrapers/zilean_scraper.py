"""
Zilean scraper (AyushSehrawat fork).

This fork uses SQLite instead of PostgreSQL, making it much simpler to deploy.
It also has improved incremental DMM pulls and retry logic.
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


class ZileanScraper(Scraper):

    name = "zilean"


    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        indexers: str | None = None,
    ):

        self.base_url = (
            base_url or settings.zilean_api_base or "http://zilean:8181"
        ).rstrip("/")

        self.api_key = (
            api_key or settings.zilean_api_key
        )

        self.indexers = (
            indexers or settings.zilean_indexers if hasattr(settings, 'zilean_indexers') else "all"
        )



    async def search(
        self,
        query: str,
        *,
        imdb_id: str | None = None,
        season: str | None = None,
        episode: str | None = None,
        media_type: str | None = None,
    ) -> list[TorrentResult]:

        if not self.base_url:
            return []

        # Zilean Torznab API endpoint
        endpoint = f"{self.base_url}/torznab/api"

        attempts = []

        if media_type == "series" and season and episode:
            try:
                s = int(season)
                e = int(episode)
                attempts.append({
                    "apikey": self.api_key,
                    "t": "tvsearch",
                    "q": query,
                    "season": s,
                    "ep": e
                })
            except ValueError:
                pass

        # Fallback to regular search
        attempts.append({
            "apikey": self.api_key,
            "t": "search",
            "q": query,
        })

        if imdb_id:
            attempts.append({
                "apikey": self.api_key,
                "t": "search",
                "q": query,
                "imdbid": imdb_id
            })

        async with httpx.AsyncClient(
            timeout=settings.scrape_timeout_seconds
        ) as client:

            for params in attempts:

                try:

                    resp = await client.get(
                        endpoint,
                        params=params,
                    )

                    if resp.status_code != 200:
                        continue

                    results = self._parse_torznab_xml(
                        resp.text
                    )

                    if results:
                        return results[:settings.max_results_per_scraper]

                except Exception:
                    # Silently fail if Zilean isn't running
                    pass

        return []



    def _parse_torznab_xml(
        self,
        xml_text: str,
    ) -> list[TorrentResult]:

        results = []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as e:
            print(f"XML PARSE ERROR: {e}", flush=True)
            return results

        for item in root.iterfind(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")

            if title_el is None or not title_el.text:
                continue

            title = title_el.text.strip()

            magnet = None
            info_hash = None
            size_bytes = None
            seeders = None
            indexer = None

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

            if not magnet and link_el is not None:
                if link_el.text and link_el.text.startswith("magnet:"):
                    magnet = link_el.text

            if not info_hash and magnet:
                match = _HASH_RE.search(magnet)
                if match:
                    info_hash = match.group(1).lower()

            if not info_hash:
                continue

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
                    indexer=indexer,
                    quality=_extract_quality(title),
                )
            )

        return results




def _extract_quality(
    title: str
) -> str | None:


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
