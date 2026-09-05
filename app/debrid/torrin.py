"""
Torrin API client and scraper.

Docs:
https://docs.torrin.app

Torrin exposes three real surfaces — there is no `/api/jobs` or
top-level `/magnets/check`:

  - /api/*        native app API (search, availability, public)
  - /rest/1.0/*   RealDebrid-compatible (torrents, unrestrict)
  - /v0/store/*   StremThru store API

This client uses /api/availability + /api/search for search/cache-check,
and /rest/1.0/torrents/* + /rest/1.0/unrestrict/link for adding magnets
and resolving playback links.
"""

import logging
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, ResolveResponse
from app.models import TorrentResult


settings = get_settings()
logger = logging.getLogger(__name__)


class TorrinClient(DebridClient):
    provider_name = "torrin"

    def __init__(self, api_key: str):
        super().__init__(api_key)

        self._base = settings.torrin_api_base.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        self._timeout = 20

    # ---------------------------------------------------------
    # CACHE CHECK
    # ---------------------------------------------------------
    # Torrin's Real-Debrid-compatible endpoint returns one object per hash:
    #   { "<hash>": { "rd": [{...}] } }
    # A non-empty rd array means the hash is cached.

    async def check_cache(
        self,
        info_hashes: list[str],
    ) -> dict[str, CacheStatus]:

        if not info_hashes:
            return {}

        normalized_hashes = [
            str(h).strip().lower()
            for h in info_hashes
            if h
        ]

        if not normalized_hashes:
            return {}

        url = (
            f"{self._base}/rest/1.0/torrents/instantAvailability/"
            f"{'/'.join(normalized_hashes)}"
        )

        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as client:

            response = await client.get(
                url,
                headers=self._headers,
            )

            response.raise_for_status()

            data = response.json()

        logger.debug(
            "Torrin cache response contained %d top-level entries",
            len(data) if isinstance(data, (dict, list)) else 0,
        )

        result: dict[str, CacheStatus] = {}

        def _status_from_value(value) -> Optional[CacheStatus]:
            if isinstance(value, dict) and "rd" in value:
                return (
                    CacheStatus.CACHED
                    if value.get("rd")
                    else CacheStatus.NOT_CACHED
                )

            # Torrin's RD-compatible endpoint returns {} for a cache miss.
            if isinstance(value, dict) and not value:
                return CacheStatus.NOT_CACHED

            if isinstance(value, bool):
                return CacheStatus.CACHED if value else CacheStatus.NOT_CACHED

            if isinstance(value, str):
                v = value.lower()
                if v == "cached":
                    return CacheStatus.CACHED
                if v in ("acceleratable", "unknown"):
                    return CacheStatus.NOT_CACHED
                return None

            if isinstance(value, dict):
                if "available" in value:
                    return (
                        CacheStatus.CACHED
                        if value.get("available")
                        else CacheStatus.NOT_CACHED
                    )
                cached = (
                    value.get("cached")
                    if "cached" in value
                    else value.get("status")
                )
                return _status_from_value(cached)

            if isinstance(value, list):
                return (
                    CacheStatus.CACHED
                    if value
                    else CacheStatus.NOT_CACHED
                )

            return None

        if isinstance(data, dict):
            for key, value in data.items():
                key_lower = str(key).lower()
                if key_lower in normalized_hashes:
                    status = _status_from_value(value)
                    if status is not None:
                        result[key_lower] = status

            entries = []
            for wrapper_key in ("results", "data", "items"):
                wrapped = data.get(wrapper_key)
                if isinstance(wrapped, list):
                    entries.extend(wrapped)
                elif isinstance(wrapped, dict):
                    nested = wrapped.get("items")
                    if isinstance(nested, list):
                        entries.extend(nested)

            for entry in entries:
                if not isinstance(entry, dict):
                    continue

                hash_value = (
                    entry.get("hash")
                    or entry.get("info_hash")
                    or entry.get("infoHash")
                )

                if not hash_value:
                    continue

                hash_value = str(hash_value).strip().lower()

                status = _status_from_value(entry)

                if status is not None:
                    result[hash_value] = status

        elif isinstance(data, list):
            for entry in data:
                if not isinstance(entry, dict):
                    continue

                hash_value = (
                    entry.get("hash")
                    or entry.get("info_hash")
                    or entry.get("infoHash")
                )

                if not hash_value:
                    continue

                hash_value = str(hash_value).strip().lower()

                status = _status_from_value(entry)

                if status is not None:
                    result[hash_value] = status

        final_result = {
            info_hash: result.get(
                info_hash,
                CacheStatus.UNKNOWN,
            )
            for info_hash in normalized_hashes
        }

        logger.info(
            "Torrin cache status: %d cached, %d uncached, %d unknown",
            sum(status == CacheStatus.CACHED for status in final_result.values()),
            sum(status == CacheStatus.NOT_CACHED for status in final_result.values()),
            sum(status == CacheStatus.UNKNOWN for status in final_result.values()),
        )

        return final_result

    # ---------------------------------------------------------
    # ACCOUNT SEARCH
    # ---------------------------------------------------------

    async def search_account(self) -> list[TorrentResult]:
        """Return recent completed torrents from the Torrin account."""

        url = f"{self._base}/rest/1.0/torrents"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            data = response.json()

        if not isinstance(data, list):
            return []

        results = []

        for torrent in data:
            if not isinstance(torrent, dict):
                continue

            if torrent.get("status") not in {"downloaded", "seeding"}:
                continue

            info_hash = str(torrent.get("hash", "")).strip().lower()
            title = str(
                torrent.get("filename")
                or torrent.get("name")
                or ""
            ).strip()

            if len(info_hash) != 40 or not title:
                continue

            results.append(
                TorrentResult(
                    title=title,
                    info_hash=info_hash,
                    magnet=f"magnet:?xt=urn:btih:{info_hash}",
                    size_bytes=torrent.get("bytes"),
                    seeders=0,
                    source="torrin-account",
                    indexer="Torrin Account",
                )
            )

        return results

    # ---------------------------------------------------------
    # ADD MAGNET
    # ---------------------------------------------------------
    # POST /rest/1.0/torrents/addMagnet — form-encoded, not JSON.

    async def add_magnet(
        self,
        magnet: str,
    ) -> str:

        url = f"{self._base}/rest/1.0/torrents/addMagnet"

        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as client:

            response = await client.post(
                url,
                headers=self._headers,
                data={"magnet": magnet},
            )

            response.raise_for_status()

            data = response.json()

        return str(data["id"])

    # ---------------------------------------------------------
    # LIST FILES
    # ---------------------------------------------------------
    # GET /rest/1.0/torrents/info/{id}

    async def list_files(
        self,
        torrent_id: str,
    ) -> list[dict]:

        url = f"{self._base}/rest/1.0/torrents/info/{torrent_id}"

        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as client:

            response = await client.get(
                url,
                headers=self._headers,
            )

            response.raise_for_status()

            data = response.json()

        return data.get("files", [])

    # ---------------------------------------------------------
    # PLAYBACK
    # ---------------------------------------------------------
    # GET /rest/1.0/torrents/info/{id} for status + links, then
    # POST /rest/1.0/unrestrict/link to turn a torrin:// link into a
    # signed, playable HTTPS URL (valid 24h).

    async def get_playback_link(
        self,
        torrent_id: str,
        file_index: Optional[int] = None,
    ) -> ResolveResponse:

        info_url = f"{self._base}/rest/1.0/torrents/info/{torrent_id}"

        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as client:

            response = await client.get(
                info_url,
                headers=self._headers,
            )

            response.raise_for_status()

            data = response.json()

        status = data.get("status", "")

        if status != "downloaded":
            raise RuntimeError(
                "Torrent not ready on Torrin "
                f"(status: {status})"
            )

        links = data.get("links", [])

        if not links:
            raise RuntimeError(
                "Torrent not ready on Torrin "
                "- no links available"
            )

        if (
            file_index is not None
            and 0 <= file_index < len(links)
        ):
            chosen_link = links[file_index]
        else:
            chosen_link = links[0]

        unrestrict_url = f"{self._base}/rest/1.0/unrestrict/link"

        async with httpx.AsyncClient(
            timeout=self._timeout
        ) as client:

            response = await client.post(
                unrestrict_url,
                headers=self._headers,
                data={"link": chosen_link},
            )

            response.raise_for_status()

            unrestrict_data = response.json()

        return ResolveResponse(
            playback_url=unrestrict_data.get("download"),
            file_name=(
                unrestrict_data.get("filename")
                or "stream"
            ),
            provider="torrin",
        )


# =========================================================
# TORRIN SCRAPER
# =========================================================

