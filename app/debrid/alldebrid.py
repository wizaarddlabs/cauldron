"""
AllDebrid API client.
Docs: https://docs.alldebrid.com/
"""
from typing import Optional

import httpx

from app.config import get_settings
from app.debrid.base import DebridClient
from app.models import CacheStatus, ResolveResponse

settings = get_settings()
AGENT = "cauldron"


class AllDebridClient(DebridClient):
    provider_name = "alldebrid"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.alldebrid_api_base
        self._params = {"agent": AGENT}
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        # AllDebrid doesn't have a publicly documented instant availability endpoint
        # like Real-Debrid or Premiumize. The endpoint may exist but requires special
        # access or has been deprecated. Return UNKNOWN to avoid misleading results.
        return {h: CacheStatus.UNKNOWN for h in info_hashes}

    async def add_magnet(self, magnet: str) -> str:
        # Use v4.1 magnet/upload endpoint
        url = f"{self._base}/magnet/upload"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={**self._params, "magnets[]": [magnet]}, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()
            magnet_info = data["data"]["magnets"][0]
            return str(magnet_info["id"])

    async def list_files(self, torrent_id: str) -> list[dict]:
        # Use v4.1 magnet/status endpoint (v4/magnet/status is deprecated)
        url = f"{self._base}/magnet/status"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={**self._params, "id": torrent_id}, headers=self._headers)
            resp.raise_for_status()
            data = resp.json()
            
            # v4.1 structure: data.magnets.files for file list
            if data.get("status") == "success":
                magnet = data.get("data", {}).get("magnets", {})
                files = magnet.get("files", [])

                # Ultra-robust parsing - try every possible structure
                parsed_files = []
                
                # Method 1: Direct file structure with 'l' field
                for file in files:
                    if not isinstance(file, dict):
                        continue
                    
                    # Try all possible field names for download link
                    link = (
                        file.get("l") or 
                        file.get("link") or 
                        file.get("url") or
                        file.get("download") or
                        file.get("stream")
                    )
                    
                    # Try all possible field names for filename
                    name = (
                        file.get("n") or 
                        file.get("name") or 
                        file.get("filename") or
                        file.get("title")
                    )
                    
                    # Try all possible field names for size
                    size = (
                        file.get("s") or 
                        file.get("size") or 
                        file.get("filesize")
                    )
                    
                    if link:
                        parsed_files.append({
                            "name": name,
                            "link": link,
                            "size": size
                        })
                
                # Method 2: If no files found, try nested structure
                if not parsed_files:
                    for file in files:
                        if isinstance(file, dict) and "e" in file:
                            entries = file["e"]
                            if isinstance(entries, list):
                                for entry in entries:
                                    if isinstance(entry, dict):
                                        link = (
                                            entry.get("l") or 
                                            entry.get("link") or 
                                            entry.get("url")
                                        )
                                        name = (
                                            entry.get("n") or 
                                            entry.get("name") or 
                                            entry.get("filename")
                                        )
                                        size = (
                                            entry.get("s") or 
                                            entry.get("size")
                                        )
                                        if link:
                                            parsed_files.append({
                                                "name": name,
                                                "link": link,
                                                "size": size
                                            })
                
                # Method 3: If still no files, try treating files as simple strings
                if not parsed_files and files:
                    for file in files:
                        if isinstance(file, str):
                            # This might be a direct download link
                            parsed_files.append({
                                "name": file,
                                "link": file,
                                "size": None
                            })
                
                return parsed_files
            else:
                return []

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        try:
            files = await self.list_files(torrent_id)
            if not files:
                raise RuntimeError("Torrent not yet ready on AllDebrid (still downloading?)")

            idx = file_index if file_index is not None and file_index < len(files) else 0
            chosen = files[idx]

            # v4.1 structure: files have link attribute
            link = chosen.get("link")
            if not link:
                raise RuntimeError("No download link available for this file")

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self._base}/link/unlock", params={**self._params, "link": link}, headers=self._headers
                )
                resp.raise_for_status()
                unlocked = resp.json()["data"]

            return ResolveResponse(
                playback_url=unlocked["link"],
                file_name=unlocked.get("filename", chosen.get("filename")),
                provider="alldebrid",
            )
        except Exception as e:
            print(f"Error getting AllDebrid playback link: {e}, torrent may not be ready", flush=True)
            raise

    async def list_user_torrents(self) -> list[dict]:
        """
        Attempts to list torrents present in the user's AllDebrid account.
        Returns a list of dicts; each dict should contain at least `hash` and
        optionally `filename` or `name` and `magnet` if available.
        This method is best-effort and returns an empty list on any failure.
        """
        try:
            url = f"{self._base}/magnet/status"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params={**self._params}, headers=self._headers)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                magnets = data.get("data", {}).get("magnets", {})
                if isinstance(magnets, dict):
                    return [
                        {
                            "hash": m.get("hash"),
                            "filename": m.get("filename"),
                            "name": m.get("filename"),
                            "size": m.get("size"),
                            "status": m.get("status")
                        }
                        for m in magnets.values()
                    ]
                return []
        except Exception:
            return []
