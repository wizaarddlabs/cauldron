"""
Torrin API client.
Docs: https://api.torrin.app/
"""
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, ResolveResponse

settings = get_settings()


class TorrinClient(DebridClient):
    provider_name = "torrin"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.torrin_api_base
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        if not info_hashes:
            return {}
        url = f"{self._base}/cache/check"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                headers=self._headers,
                json={"hashes": info_hashes},
            )
            resp.raise_for_status()
            data = resp.json()

        cached_hashes = {
            item.get("hash", "").lower() for item in data.get("cached", []) if isinstance(item, dict)
        }
        return {
            h: (CacheStatus.CACHED if h.lower() in cached_hashes else CacheStatus.NOT_CACHED)
            for h in info_hashes
        }

    async def add_magnet(self, magnet: str) -> str:
        url = f"{self._base}/torrents/add"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url, headers=self._headers, json={"magnet": magnet}
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["id"])

    async def list_files(self, torrent_id: str) -> list[dict]:
        url = f"{self._base}/torrents/{torrent_id}/files"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url, headers=self._headers
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("files", [])

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        # First try to get files - if it's already added
        try:
            files = await self.list_files(torrent_id)
            if files:
                idx = file_index if file_index is not None and file_index < len(files) else 0
                chosen = files[idx]

                url = f"{self._base}/torrents/{torrent_id}/download"
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        url,
                        headers=self._headers,
                        params={"file_id": chosen.get("id")},
                    )
                    resp.raise_for_status()
                    data = resp.json()

                return ResolveResponse(
                    playback_url=data["url"],
                    file_name=chosen.get("name"),
                    provider="torrin",
                )
        except Exception as e:
            print(f"Error getting existing files: {e}, trying direct request", flush=True)
        
        # If torrent not in user list or error, request download and get playback link
        url = f"{self._base}/torrents/{torrent_id}/download"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

        return ResolveResponse(
            playback_url=data["url"],
            file_name="stream",
            provider="torrin",
        )
