"""
Premiumize API client.
Docs: https://app.premiumize.me/api
"""
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, ResolveResponse

settings = get_settings()


class PremiumizeClient(DebridClient):
    provider_name = "premiumize"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.premiumize_api_base
        self._params = {"apikey": api_key}

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        if not info_hashes:
            return {}
        url = f"{self._base}/cache/check"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url, params={**self._params, "items[]": [f"magnet:?xt=urn:btih:{h}" for h in info_hashes]}
            )
            resp.raise_for_status()
            data = resp.json()

        response_list = data.get("response", [])
        result: dict[str, CacheStatus] = {}
        for h, cached in zip(info_hashes, response_list):
            result[h] = CacheStatus.CACHED if cached else CacheStatus.NOT_CACHED
        return result

    async def add_magnet(self, magnet: str) -> str:
        url = f"{self._base}/transfer/create"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, params=self._params, data={"src": magnet})
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("id", data.get("name", "")))

    async def list_files(self, torrent_id: str) -> list[dict]:
        # Premiumize is cache-first: for already-cached items, browse the
        # generated folder directly rather than polling a transfer job.
        url = f"{self._base}/folder/list"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={**self._params, "id": torrent_id})
            resp.raise_for_status()
            data = resp.json()
            return data.get("content", [])

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        files = await self.list_files(torrent_id)
        streamable = [f for f in files if f.get("type") == "file" and f.get("stream_link")]
        if not streamable:
            raise RuntimeError("No streamable files found for this item on Premiumize")

        idx = file_index if file_index is not None and file_index < len(streamable) else 0
        chosen = streamable[idx]

        return ResolveResponse(
            playback_url=chosen["stream_link"],
            file_name=chosen.get("name"),
            provider="premiumize",
        )
