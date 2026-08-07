"""
Public torrent site scrapers - no external services required.

Sources:
- The Pirate Bay (via apibay.org API)
- 1337x (web scraping)
- YTS (API)
- Nyaa (web scraping) - Anime-focused
"""

import re
import asyncio
from urllib.parse import quote, urljoin
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings
from app.models import TorrentResult
from app.scrapers.base import Scraper


settings = get_settings()

# Quality extraction patterns
_QUALITY_PATTERN = re.compile(
    r"\b(2160p|4K|1080p|720p|480p|CAM|HDCAM|TS|WEBRip|BluRay|DVDRip)\b",
    re.IGNORECASE
)

# Size parsing patterns
_SIZE_PATTERN = re.compile(r"(\d+\.?\d*)\s*(GB|MB|KB|TB)", re.IGNORECASE)


class PublicScraper(Scraper):
    """
    Aggregates results from multiple public torrent sources.
    Falls back between sources if one fails.
    """

    name = "public"

    def __init__(self):
        self.timeout = settings.scrape_timeout_seconds
        self.max_results = settings.max_results_per_scraper if hasattr(settings, 'max_results_per_scraper') else 50

    async def search(
        self,
        query: str,
        *,
        imdb_id: str | None = None,
        season: str | None = None,
        episode: str | None = None,
        media_type: str | None = None,
    ) -> list[TorrentResult]:
        """
        Search across all public sources and merge results.
        """
        all_results = []

        # Build search queries
        queries = self._build_queries(query, season, episode, media_type)

        # Search each source concurrently
        tasks = [
            self._search_tpb(queries, imdb_id),
            self._search_1337x(queries),
            self._search_yts(queries, imdb_id),
            self._search_nyaa(queries),
        ]

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        for results in results_lists:
            if isinstance(results, Exception):
                continue
            if isinstance(results, list):
                all_results.extend(results)

        # Deduplicate by info_hash
        seen_hashes = set()
        unique_results = []
        for result in all_results:
            if result.info_hash not in seen_hashes:
                seen_hashes.add(result.info_hash)
                unique_results.append(result)

        # Sort by seeders and limit results
        unique_results.sort(key=lambda r: r.seeders or 0, reverse=True)
        return unique_results[:self.max_results]

    def _build_queries(
        self,
        query: str,
        season: str | None = None,
        episode: str | None = None,
        media_type: str | None = None,
    ) -> list[str]:
        """Build multiple query variations for better results."""
        queries = [query]

        # TV episode formatting
        if media_type == "series" and season and episode:
            try:
                s = int(season)
                e = int(episode)
                queries.extend([
                    f"{query} S{s:02d}E{e:02d}",
                    f"{query} Season {s} Episode {e}",
                    f"{query} {s}x{e}",
                ])
            except ValueError:
                pass


        return list(dict.fromkeys(queries))  # Remove duplicates

    async def _search_tpb(
        self,
        queries: list[str],
        imdb_id: str | None = None,
    ) -> list[TorrentResult]:
        """Search The Pirate Bay via apibay.org API."""
        results = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Only try the first 5 queries to avoid excessive requests
                for query in queries[:5]:
                    try:
                        # TPB API via apibay.org
                        url = f"https://apibay.org/q.php?q={quote(query)}"
                        resp = await client.get(url)

                        if resp.status_code != 200:
                            continue

                        data = resp.json()

                        if not isinstance(data, list) or len(data) == 0:
                            continue

                        for item in data:
                            if not isinstance(item, dict):
                                continue

                            info_hash = item.get("info_hash")
                            if not info_hash:
                                continue

                            # Parse seeders/leechers
                            try:
                                seeders = int(item.get("seeders", 0))
                            except (ValueError, TypeError):
                                seeders = 0

                            # Parse size
                            size_bytes = self._parse_size(item.get("size", ""))

                            magnet = f"magnet:?xt=urn:btih:{info_hash}&dn={quote(item.get('name', ''))}"

                            results.append(TorrentResult(
                                title=item.get("name", ""),
                                info_hash=info_hash.lower(),
                                magnet=magnet,
                                size_bytes=size_bytes,
                                seeders=seeders,
                                source="thepiratebay",
                                indexer="ThePirateBay",
                                quality=_extract_quality(item.get("name", "")),
                            ))

                    except Exception:
                        continue

        except Exception:
            pass

        return results

    async def _search_1337x(self, queries: list[str]) -> list[TorrentResult]:
        """Search 1337x via web scraping."""
        results = []

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0"}
            ) as client:
                # Only try the first 3 queries to avoid rate limiting
                for query in queries[:3]:
                    try:
                        # 1337x search page
                        url = f"https://www.1337xx.to/search/{quote(query)}/1/"
                        resp = await client.get(url)

                        if resp.status_code != 200:
                            continue

                        # Parse HTML for torrent links
                        # Look for torrent rows in the search results
                        html = resp.text

                        # Extract torrent links and info
                        # This is a simplified parser - 1337x structure may change
                        pattern = re.compile(
                            r'<a href="/torrent/(\d+)/([^/]+)/?".*?'
                            r'<span class="seeds">(\d+)</span>.*?'
                            r'<span class="leeches">(\d+)</span>.*?'
                            r'<span class="size">(\d+\.?\d*\s*[GMK]B)</span>',
                            re.DOTALL | re.IGNORECASE
                        )

                        matches = pattern.findall(html)

                        for match in matches:
                            torrent_id, slug, seeders, leechers, size = match

                            # Get the magnet link from the torrent page
                            try:
                                torrent_url = f"https://www.1337xx.to/torrent/{torrent_id}/{slug}/"
                                torrent_resp = await client.get(
                                    torrent_url,
                                    headers={"User-Agent": "Mozilla/5.0"}
                                )

                                if torrent_resp.status_code == 200:
                                    magnet_match = re.search(
                                        r'magnet:\?xt=urn:btih:([a-fA-F0-9]{40})',
                                        torrent_resp.text
                                    )

                                    if magnet_match:
                                        info_hash = magnet_match.group(1).lower()
                                        magnet = f"magnet:?xt=urn:btih:{info_hash}"

                                        results.append(TorrentResult(
                                            title=slug.replace("-", " "),
                                            info_hash=info_hash,
                                            magnet=magnet,
                                            size_bytes=self._parse_size(size),
                                            seeders=int(seeders) if seeders.isdigit() else 0,
                                            source="1337x",
                                            indexer="1337x",
                                            quality=_extract_quality(slug),
                                        ))

                                        if len(results) >= self.max_results:
                                            break

                            except Exception:
                                continue

                        if len(results) >= self.max_results:
                            break

                    except Exception:
                        continue

        except Exception:
            pass

        return results

    async def _search_yts(
        self,
        queries: list[str],
        imdb_id: str | None = None,
    ) -> list[TorrentResult]:
        """Search YTS via their API."""
        results = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # YTS API endpoint
                base_url = "https://yts.mx/api/v2/list_movies.json"

                # Only try the first 3 queries for YTS
                for query in queries[:3]:
                    try:
                        params = {"query_term": query, "limit": 20}

                        resp = await client.get(base_url, params=params)

                        if resp.status_code != 200:
                            continue

                        data = resp.json()

                        if data.get("status") != "ok":
                            continue

                        movies = data.get("data", {}).get("movies", [])

                        for movie in movies:
                            torrents = movie.get("torrents", [])

                            for torrent in torrents:
                                info_hash = torrent.get("hash")
                                if not info_hash:
                                    continue

                                quality = torrent.get("quality", "")
                                size = torrent.get("size", "")
                                seeders = torrent.get("seeds", 0)

                                magnet = f"magnet:?xt=urn:btih:{info_hash}"

                                results.append(TorrentResult(
                                    title=movie.get("title_long", movie.get("title", "")),
                                    info_hash=info_hash.lower(),
                                    magnet=magnet,
                                    size_bytes=self._parse_size(size),
                                    seeders=int(seeders) if seeders else 0,
                                    source="yts",
                                    indexer="YTS",
                                    quality=quality,
                                ))

                            if len(results) >= self.max_results:
                                break

                    except Exception:
                        continue

        except Exception:
            pass

        return results

    async def _search_nyaa(
        self,
        queries: list[str],
    ) -> list[TorrentResult]:
        """Search Nyaa.si for anime torrents."""
        print("Starting Nyaa search...", flush=True)
        results = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Only try the first 3 queries for Nyaa
                for query in queries[:3]:
                    try:
                        print(f"Nyaa searching for: {query}", flush=True)
                        # Nyaa.si search URL
                        url = f"https://nyaa.si/?q={quote(query)}&s=seeders&o=desc"
                        headers = {"User-Agent": "Mozilla/5.0"}

                        resp = await client.get(url, headers=headers)
                        print(f"Nyaa response status: {resp.status_code}", flush=True)

                        if resp.status_code != 200:
                            continue

                        soup = BeautifulSoup(resp.text, "html.parser")

                        # Find torrent rows - Nyaa uses tbody structure
                        rows = soup.select("tbody tr")
                        print(f"Nyaa found {len(rows)} rows", flush=True)

                        for row in rows[1:]:  # Skip header row
                            try:
                                cols = row.select("td")
                                if len(cols) < 4:
                                    continue

                                # Extract magnet link
                                magnet_link = cols[2].select_one("a[href^='magnet:']")
                                if not magnet_link:
                                    continue

                                magnet = magnet_link["href"]
                                magnet_match = re.search(
                                    r'magnet:\?xt=urn:btih:([a-fA-F0-9]{40})',
                                    magnet
                                )

                                if not magnet_match:
                                    continue

                                info_hash = magnet_match.group(1).lower()

                                # Extract title
                                title_link = cols[1].select_one("a")
                                title = title_link.text.strip() if title_link else ""

                                # Extract seeders and leechers
                                seeders = 0
                                leechers = 0
                                try:
                                    seeders = int(cols[3].text.strip())
                                    leechers = int(cols[4].text.strip())
                                except (ValueError, AttributeError):
                                    pass

                                # Extract size
                                size_str = cols[1].text.strip()
                                size_match = re.search(r'\d+\.?\d*\s*[GMK]B', size_str, re.IGNORECASE)
                                size = size_match.group(0) if size_match else ""

                                results.append(TorrentResult(
                                    title=title,
                                    info_hash=info_hash,
                                    magnet=magnet,
                                    size_bytes=self._parse_size(size),
                                    seeders=seeders,
                                    leechers=leechers,
                                    source="nyaa",
                                    indexer="Nyaa",
                                    quality=_extract_quality(title),
                                ))

                                if len(results) >= self.max_results:
                                    break

                            except Exception:
                                continue

                        if len(results) >= self.max_results:
                            break

                    except Exception as e:
                        print(f"Nyaa query error: {e}", flush=True)
                        continue

            print(f"Nyaa scraper returned {len(results)} results", flush=True)

        except Exception as e:
            print(f"Nyaa scraper error: {e}", flush=True)

        return results

    def _parse_size(self, size_str: str) -> int | None:
        """Parse size string like '1.5 GB' to bytes."""
        if not size_str:
            return None

        match = _SIZE_PATTERN.search(size_str)
        if not match:
            return None

        try:
            value = float(match.group(1))
            unit = match.group(2).upper()

            multipliers = {
                "KB": 1024,
                "MB": 1024 ** 2,
                "GB": 1024 ** 3,
                "TB": 1024 ** 4,
            }

            return int(value * multipliers.get(unit, 1))
        except (ValueError, TypeError):
            return None


def _extract_quality(title: str) -> str | None:
    """Extract quality from torrent title."""
    if not title:
        return None

    match = _QUALITY_PATTERN.search(title)
    if match:
        return match.group(1).upper()

    return None
