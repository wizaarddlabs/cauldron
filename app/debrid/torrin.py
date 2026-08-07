"""
Torrin API client.
Docs: https://docs.torrin.app
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
        self._base = settings.torrin_api_base.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}
        # Torrin can be slower due to download/cache processing
        self._timeout = 60

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        if not info_hashes:
            return {}

        url = f"{self._base}/api/availability"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url,
                headers=self._headers,
                json={"hashes": info_hashes},
            )
            resp.raise_for_status()
            data = resp.json()

        # Torrin returns availability data with cached status
        result = {}
        for h in info_hashes:
            # Check if hash is in the response and marked as available
            if h in data:
                result[h] = CacheStatus.CACHED if data[h].get("cached", False) else CacheStatus.NOT_CACHED
            else:
                result[h] = CacheStatus.NOT_CACHED

        return result

    async def add_magnet(self, magnet: str) -> str:
        url = f"{self._base}/api/jobs"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url,
                headers=self._headers,
                json={"magnet": magnet},
            )
            resp.raise_for_status()
            data = resp.json()
            # Torrin returns job ID
            return str(data["id"])

    async def list_files(self, torrent_id: str) -> list[dict]:
        # Get job info which includes file list
        url = f"{self._base}/api/jobs/{torrent_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            # Return stream_urls or files from the job
            return data.get("stream_urls", [])

    async def list_user_torrents(self) -> list[dict]:
        """
        Attempts to list torrents present in the user's Torrin account.
        Returns a list of dicts; each dict should contain at least `hash` and
        optionally `filename` or `name` and `magnet` if available.
        This method is best-effort and returns an empty list on any failure.
        """
        try:
            url = f"{self._base}/api/jobs"
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url,
                    headers=self._headers,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                # Torrin returns a list of jobs
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            return []

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        # Get job info which includes playback URLs
        url = f"{self._base}/api/jobs/{torrent_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # Check job status
        status = data.get("status", "")
        if status not in ["completed", "cached"]:
            raise RuntimeError(f"Torrent not ready on Torrin (status: {status})")

        # Get stream URLs
        stream_urls = data.get("stream_urls", [])
        if not stream_urls:
            raise RuntimeError("Torrent not ready on Torrin - no stream URLs available")

        # Select appropriate stream URL
        idx = file_index if file_index is not None and file_index < len(stream_urls) else 0
        chosen = stream_urls[idx]

        # Torrin returns signed URLs directly
        return ResolveResponse(
            playback_url=chosen.get("signed_url", chosen.get("url")),
            file_name=chosen.get("filename", chosen.get("name", "stream")),
            provider="torrin",
        )
