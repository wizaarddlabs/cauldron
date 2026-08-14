"""
MediaFusion Stremio-addon scraper.

MediaFusion exposes torrent results through its standard Stremio stream API:

    /stream/movie/<imdb_id>.json
    /stream/series/<imdb_id>:<season>:<episode>.json

Cauldron consumes the torrent metadata returned by MediaFusion and converts
it into TorrentResult objects. Any playback/debrid URLs are intentionally
ignored because Cauldron handles debrid resolution itself.
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote

import httpx

from app.config import get_settings
from app.models import TorrentResult
from app.scrapers.base import Scraper


settings = get_settings()


_INFO_HASH_RE = re.compile(
    r"^[0-9a-fA-F]{40}$"
)

_QUALITY_RE = re.compile(
    r"\b(2160p|1080p|720p|576p|480p|360p|240p|4k)\b",
    re.IGNORECASE,
)

_CODEC_RE = re.compile(
    r"\b(av1|avc|h\.?264|x264|h\.?265|x265|hevc|xvid)\b",
    re.IGNORECASE,
)

_SEEDERS_RE = re.compile(
    r"👤\s*([\d,]+)",
)

_INDEXER_RE = re.compile(
    r"(?:🔗|🔎)\s*(.+?)(?:\n|$)",
)


class MediaFusionScraper(Scraper):
    """Scrape torrent metadata from the configured MediaFusion instance."""

    name = "mediafusion"

    def __init__(self) -> None:
        self.base_url = "https://mediafusion.forthewizards.uk"
        self.timeout = settings.scrape_timeout_seconds

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
        Query MediaFusion's Stremio stream endpoint.

        MediaFusion is ID-driven, so an IMDb ID is required.
        """

        if not imdb_id:
            return []

        imdb_id = str(imdb_id).strip()

        if not imdb_id.startswith("tt"):
            return []

        if media_type == "series":
            if season is None or episode is None:
                return []

            try:
                season_num = int(season)
                episode_num = int(episode)
            except (TypeError, ValueError):
                return []

            endpoint = (
                f"{self.base_url}/stream/series/"
                f"{imdb_id}:{season_num}:{episode_num}.json"
            )

        else:
            endpoint = (
                f"{self.base_url}/stream/movie/"
                f"{imdb_id}.json"
            )

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Cauldron/0.0.3",
                },
            ) as client:
                response = await client.get(endpoint)
                response.raise_for_status()
                payload = response.json()

        except Exception:
            return []

        if not isinstance(payload, dict):
            return []

        streams = payload.get("streams")

        if not isinstance(streams, list):
            return []

        results: list[TorrentResult] = []
        seen_hashes: set[str] = set()

        for stream in streams:
            if not isinstance(stream, dict):
                continue

            info_hash = str(
                stream.get("infoHash")
                or stream.get("info_hash")
                or ""
            ).strip().lower()

            if not _INFO_HASH_RE.fullmatch(info_hash):
                continue

            if info_hash in seen_hashes:
                continue

            filename = self._extract_filename(stream)

            if not filename:
                filename = (
                    stream.get("title")
                    or stream.get("name")
                    or query
                    or imdb_id
                )

            filename = str(filename).strip()

            description = str(
                stream.get("description") or ""
            )

            size_bytes = self._extract_size(stream)

            seeders = self._extract_seeders(description)

            indexer = self._extract_indexer(description)

            quality = self._extract_quality(
                stream,
                filename,
            )

            codec = self._extract_codec(
                stream,
                filename,
                description,
            )

            magnet = self._build_magnet(
                info_hash,
                filename,
                stream.get("sources"),
            )

            results.append(
                TorrentResult(
                    title=filename,
                    info_hash=info_hash,
                    magnet=magnet,
                    size_bytes=size_bytes,
                    seeders=seeders,
                    leechers=None,
                    source=self.name,
                    indexer=indexer,
                    quality=quality,
                    codec=codec,
                    published_at=None,
                )
            )

            seen_hashes.add(info_hash)

            if len(results) >= settings.max_results_per_scraper:
                break

        return results

    # =========================================================
    # PARSING
    # =========================================================

    @staticmethod
    def _extract_filename(stream: dict) -> str | None:
        behavior_hints = stream.get("behaviorHints")

        if isinstance(behavior_hints, dict):
            filename = behavior_hints.get("filename")

            if filename:
                return str(filename)

        filename = stream.get("filename")

        if filename:
            return str(filename)

        return None

    @staticmethod
    def _extract_size(stream: dict) -> int | None:
        behavior_hints = stream.get("behaviorHints")

        if isinstance(behavior_hints, dict):
            value = behavior_hints.get("videoSize")

            if isinstance(value, int):
                return value

            if isinstance(value, float):
                return int(value)

            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    pass

        for key in (
            "videoSize",
            "sizeBytes",
            "size_bytes",
        ):
            value = stream.get(key)

            if isinstance(value, int):
                return value

            if isinstance(value, float):
                return int(value)

            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    pass

        return None

    @staticmethod
    def _extract_seeders(description: str) -> int | None:
        match = _SEEDERS_RE.search(description)

        if not match:
            return None

        try:
            return int(
                match.group(1).replace(",", "")
            )
        except ValueError:
            return None

    @staticmethod
    def _extract_indexer(description: str) -> str | None:
        match = _INDEXER_RE.search(description)

        if not match:
            return None

        value = match.group(1).strip()

        if not value:
            return None

        return value

    @staticmethod
    def _extract_quality(
        stream: dict,
        filename: str,
    ) -> str | None:

        for value in (
            stream.get("name"),
            filename,
        ):
            if not value:
                continue

            match = _QUALITY_RE.search(
                str(value)
            )

            if match:
                quality = match.group(1)

                if quality.lower() == "4k":
                    return "2160p"

                return quality.lower()

        return None

    @staticmethod
    def _extract_codec(
        stream: dict,
        filename: str,
        description: str,
    ) -> str | None:

        for value in (
            filename,
            description,
            stream.get("name"),
        ):
            if not value:
                continue

            match = _CODEC_RE.search(
                str(value)
            )

            if match:
                codec = match.group(1).lower()

                if codec in {"h.264", "x264", "avc"}:
                    return "h264"

                if codec in {
                    "h.265",
                    "x265",
                    "hevc",
                }:
                    return "hevc"

                return codec

        return None

    @staticmethod
    def _build_magnet(
        info_hash: str,
        filename: str,
        sources,
    ) -> str:
        """
        Build a conventional magnet URI.

        MediaFusion supplies infoHash separately from tracker sources.
        Preserve usable tracker URLs when available and ignore DHT-only
        entries.
        """

        magnet = (
            f"magnet:?xt=urn:btih:{info_hash}"
            f"&dn={quote(filename, safe='')}"
        )

        if not isinstance(sources, list):
            return magnet

        seen_trackers: set[str] = set()

        for source in sources:
            if not isinstance(source, str):
                continue

            source = unquote(source.strip())

            if source.startswith("tracker:"):
                tracker = source[len("tracker:"):]

            elif source.startswith(
                (
                    "udp://",
                    "http://",
                    "https://",
                )
            ):
                tracker = source

            else:
                continue

            if not tracker:
                continue

            if tracker in seen_trackers:
                continue

            seen_trackers.add(tracker)

            magnet += (
                "&tr="
                + quote(
                    tracker,
                    safe=":/?=&;%+-._~",
                )
            )

        return magnet
