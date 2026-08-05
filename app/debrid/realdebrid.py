"""
Real-Debrid API client.
Docs: https://api.real-debrid.com/
"""
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, ResolveResponse

settings = get_settings()


class RealDebridClient(DebridClient):
    provider_name = "realdebrid"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.realdebrid_api_base
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        """
        Real-Debrid's instant-availability endpoint accepts up to many hashes
        in a single path-segment request.
        """
        if not info_hashes:
            return {}
        hashes_path = "/".join(h.lower() for h in info_hashes)
        url = f"{self._base}/torrents/instantAvailability/{hashes_path}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()

        result: dict[str, CacheStatus] = {}
        for h in info_hashes:
            entry = data.get(h.lower()) or data.get(h.upper())
            has_files = bool(entry) and any(entry.get(k) for k in entry.keys())
            result[h] = CacheStatus.CACHED if has_files else CacheStatus.NOT_CACHED
        return result

    async def add_magnet(self, magnet: str) -> str:
        url = f"{self._base}/torrents/addMagnet"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=self._headers, data={"magnet": magnet})
            resp.raise_for_status()
            torrent_id = resp.json()["id"]

            # Select all files by default so RD starts caching/downloading.
            select_url = f"{self._base}/torrents/selectFiles/{torrent_id}"
            await client.post(select_url, headers=self._headers, data={"files": "all"})

        return torrent_id

    async def list_files(self, torrent_id: str) -> list[dict]:
        url = f"{self._base}/torrents/info/{torrent_id}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("files", [])

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        async with httpx.AsyncClient(timeout=15) as client:
            info_resp = await client.get(
                f"{self._base}/torrents/info/{torrent_id}", headers=self._headers
            )
            info_resp.raise_for_status()
            info = info_resp.json()
            links = info.get("links", [])
            if not links:
                raise RuntimeError("Torrent not yet ready on Real-Debrid (still downloading?)")

            # Pick the requested link, or the first available.
            idx = file_index if file_index is not None and file_index < len(links) else 0
            restricted_link = links[idx]

            unrestrict_resp = await client.post(
                f"{self._base}/unrestrict/link",
                headers=self._headers,
                data={"link": restricted_link},
            )
            unrestrict_resp.raise_for_status()
            unrestricted = unrestrict_resp.json()

        return ResolveResponse(
            playback_url=unrestricted["download"],
            file_name=unrestricted.get("filename"),
            provider="realdebrid",
        )
