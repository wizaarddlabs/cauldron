"""
Offcloud API client.
Docs: https://github.com/offcloud/offcloud-api

IMPORTANT:
- Auth is done via the `?key=[api_key]` query parameter, NOT an
  Authorization header.
- All parameters are sent as POST form variables.
- Adding a magnet works by passing the magnet URI in the `url` field.
- A cloud request id is used to browse files and to fetch a direct
  download link for a specific file.
"""
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, DebridProvider, ResolveResponse


settings = get_settings()


class OffcloudClient(DebridClient):
    provider_name = "offcloud"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.offcloud_api_base.rstrip("/")

    def _url(self, path: str) -> str:
        """Build a URL with the API key as the ?key= query param."""
        return f"{self._base}/{path}?key={self.api_key}"
    
    def _explore_url(self, request_id: str) -> str:
        """Build an explore URL with requestId in path."""
        return f"{self._base}/cloud/explore/{request_id}?key={self.api_key}"
    
    def _download_url(self, request_id: str, file_id: str) -> str:
        """Build a download URL with requestId and fileId in path."""
        return f"{self._base}/cloud/download/{request_id}/{file_id}?key={self.api_key}"

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        """
        Check which info hashes are cached on Offcloud.
        
        Uses the Offcloud /api/cache endpoint to check instant availability.
        """
        if not info_hashes:
            return {}
        
        url = self._url("cache")
        
        result = {}
        
        # Offcloud accepts hashes as a JSON array in POST data
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    url,
                    json={
                        "hashes": info_hashes
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                
                # Parse the response - Offcloud returns cachedItems array
                cached_items = data.get("cachedItems", [])
                
                # Mark hashes based on response
                for h in info_hashes:
                    if h in cached_items:
                        result[h] = CacheStatus.CACHED
                    else:
                        # If hash not in cached list, treat as not cached
                        result[h] = CacheStatus.NOT_CACHED
                        
            except Exception as e:
                # On error, return unknown for all hashes
                print(f"Offcloud cache check error: {e}", flush=True)
                return {h: CacheStatus.UNKNOWN for h in info_hashes}
        
        return result

    async def add_magnet(self, magnet: str) -> str:
        """
        Add a magnet link to the Offcloud cloud.

        Offcloud accepts magnet URIs in the `url` POST field. The response's
        `requestId` becomes the torrent id used for later browsing/playback.
        """
        url = self._url("cloud")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                data={
                    "url": magnet,
                    "format": "magnet",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        request_id = str(data.get("requestId", "")).strip()

        if not request_id:
            error = data.get("error") or data.get("not_available") or "unknown"
            raise RuntimeError(f"Offcloud failed to add magnet: {error}")

        return request_id

    async def list_files(self, torrent_id: str) -> list[dict]:
        """List the files stored within a cloud request."""
        # According to Offcloud API docs, explore is a GET request with requestId in URL path
        url = self._explore_url(torrent_id)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        # Offcloud returns a simple array of download URLs, not file objects
        if isinstance(data, list):
            # Convert URLs to file objects with index as ID
            return [
                {
                    "id": str(i),  # Use index as file ID
                    "name": url.split("/")[-1].replace("%20", " ").replace("%5B", "[").replace("%5D", "]"),
                    "size": 0,  # Size not provided in response
                    "url": url  # Store the actual URL for download
                }
                for i, url in enumerate(data)
            ]
        
        # Fallback for other response formats
        files = data.get("files", []) if isinstance(data, dict) else []
        if not isinstance(files, list):
            return []

        return [
            {
                "id": f.get("fileId"),
                "name": f.get("fileName"),
                "size": f.get("size"),
            }
            for f in files
            if isinstance(f, dict)
        ]

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        try:
            files = await self.list_files(torrent_id)

            if not files:
                raise RuntimeError("Torrent not found or ready on Offcloud")

            idx = (
                file_index
                if file_index is not None and file_index < len(files)
                else 0
            )

            chosen = files[idx]

            # Check if the file already has a direct URL (from explore response)
            if "url" in chosen:
                download_url = chosen["url"]
            else:
                # Use the download endpoint if URL not available
                if not chosen.get("id"):
                    raise RuntimeError("No file id found for this file on Offcloud")

                # Fetch a direct download link for the chosen file.
                url = self._download_url(torrent_id, chosen["id"])

                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    data = resp.json()

                download_url = data.get("url")

            if not download_url:
                raise RuntimeError(
                    "No download link available on Offcloud "
                    "(torrent may still be downloading)"
                )

            return ResolveResponse(
                playback_url=download_url,
                file_name=chosen.get("name"),
                provider="offcloud",
            )

        except Exception as e:
            print(
                f"Error getting Offcloud playback link: {e}, "
                "torrent may not be ready",
                flush=True,
            )
            raise
