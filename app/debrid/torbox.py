"""
TorBox API client.
Docs: https://api-docs.torbox.app/
"""
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, ResolveResponse

settings = get_settings()


class TorBoxClient(DebridClient):
    provider_name = "torbox"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.torbox_api_base
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        if not info_hashes:
            return {}
        url = f"{self._base}/torrents/checkcached"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers=self._headers,
                params={"hash": ",".join(info_hashes), "format": "list"},
            )
            resp.raise_for_status()
            data = resp.json()

        cached_hashes = {
            item.get("hash", "").lower() for item in data.get("data", []) if isinstance(item, dict)
        }
        return {
            h: (CacheStatus.CACHED if h.lower() in cached_hashes else CacheStatus.NOT_CACHED)
            for h in info_hashes
        }

    async def add_magnet(self, magnet: str) -> str:
        url = f"{self._base}/torrents/createtorrent"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url, headers=self._headers, data={"magnet": magnet, "seed": 1}
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["data"]["torrent_id"])

    async def list_files(self, torrent_id: str) -> list[dict]:
        url = f"{self._base}/torrents/mylist"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url, headers=self._headers, params={"id": torrent_id, "bypass_cache": "true"}
            )
            resp.raise_for_status()
            data = resp.json()
            item = data.get("data")
            if isinstance(item, list):
                item = item[0] if item else {}
            return (item or {}).get("files", [])

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        files = await self.list_files(torrent_id)
        if not files:
            raise RuntimeError("Torrent not yet ready on TorBox (still downloading?)")

        idx = file_index if file_index is not None and file_index < len(files) else 0
        chosen = files[idx]

        url = f"{self._base}/torrents/requestdl"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers=self._headers,
                params={"token": self.api_key, "torrent_id": torrent_id, "file_id": chosen["id"]},
            )
            resp.raise_for_status()
            data = resp.json()

        return ResolveResponse(
            playback_url=data["data"],
            file_name=chosen.get("name") or chosen.get("short_name"),
            provider="torbox",
        )
