"""
Premiumize API client.
Docs: https://www.premiumize.me/api

IMPORTANT: /api/transfer/create returns a TRANSFER id, not a folder or
file id, and it is not directly browsable. You must poll /api/transfer/list
to find that transfer's status; once status is "finished" or "seeding" it
carries either a folder_id (multi-file torrent -> browse via folder/list)
or a file_id (single-file transfer -> fetch via item/details). Calling
folder/list directly with the raw transfer id (the old behaviour here)
always fails with "Folder not found or not owned by user."

Also: stream_link is deprecated -- Premiumize's transcode infra was
retired, so stream_link is null for nearly everything now. Use `link`.
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
        # This id is a TRANSFER id. It must be resolved via transfer/list
        # (see _get_transfer_status) to obtain a folder_id or file_id
        # before anything can be browsed or played.
        url = f"{self._base}/transfer/create"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, params=self._params, data={"src": magnet})
            resp.raise_for_status()
            data = resp.json()
            return str(data.get("id", data.get("name", "")))

    async def _get_transfer_status(self, transfer_id: str) -> Optional[dict]:
        """Find a transfer's current status/folder_id/file_id via transfer/list."""
        url = f"{self._base}/transfer/list"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=self._params)
            resp.raise_for_status()
            data = resp.json()
        for transfer in data.get("transfers", []):
            if transfer.get("id") == transfer_id:
                return transfer
        return None

    async def _list_folder(self, folder_id: str) -> list[dict]:
        url = f"{self._base}/folder/list"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={**self._params, "id": folder_id})
            resp.raise_for_status()
            data = resp.json()
        return data.get("content", [])

    async def list_files(self, torrent_id: str) -> list[dict]:
        # torrent_id here is a TRANSFER id -- resolve to folder_id first.
        transfer = await self._get_transfer_status(torrent_id)
        if not transfer:
            return []
        folder_id = transfer.get("folder_id")
        if not folder_id:
            return []
        return await self._list_folder(folder_id)

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        try:
            transfer = await self._get_transfer_status(torrent_id)
            if not transfer:
                raise RuntimeError("Transfer not found on Premiumize")

            status = transfer.get("status")
            if status not in ("finished", "seeding"):
                raise RuntimeError(
                    f"Transfer not ready on Premiumize (status: {status})"
                )

            file_id = transfer.get("file_id")
            folder_id = transfer.get("folder_id")

            if file_id:
                # Single-file transfer -- item/details gives the link directly.
                url = f"{self._base}/item/details"
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, params={**self._params, "id": file_id})
                    resp.raise_for_status()
                    item = resp.json()
                if not item.get("link"):
                    raise RuntimeError("No playable link found for this item on Premiumize")
                return ResolveResponse(
                    playback_url=item["link"],
                    file_name=item.get("name"),
                    provider="premiumize",
                )

            if folder_id:
                files = await self._list_folder(folder_id)
                streamable = [f for f in files if f.get("type") == "file" and f.get("link")]
                if not streamable:
                    raise RuntimeError("No streamable files found for this item on Premiumize")
                idx = file_index if file_index is not None and file_index < len(streamable) else 0
                chosen = streamable[idx]
                return ResolveResponse(
                    playback_url=chosen["link"],
                    file_name=chosen.get("name"),
                    provider="premiumize",
                )

            raise RuntimeError("Transfer finished but produced no file or folder on Premiumize")

        except Exception as e:
            print(f"Error getting Premiumize playback link: {e}, torrent may not be ready", flush=True)
            raise
