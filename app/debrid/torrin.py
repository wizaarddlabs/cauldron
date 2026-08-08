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
        # Use RealDebrid-compatible endpoints
        self._rd_base = f"{self._base}/rest/1.0"

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        if not info_hashes:
            return {}

        # Use RealDebrid-compatible instant availability endpoint
        # GET /rest/1.0/torrents/instantAvailability/{hash1}/{hash2}/...
        result = {}
        
        print(f"Torrin cache check: {len(info_hashes)} hashes", flush=True)
        
        # Batch size for instant availability (RD supports up to ~100 at once)
        batch_size = 50
        
        for i in range(0, len(info_hashes), batch_size):
            batch = info_hashes[i:i + batch_size]
            
            # Join hashes with slashes for RD-compatible endpoint
            hashes_path = "/".join(h.lower() for h in batch)
            url = f"{self._rd_base}/torrents/instantAvailability/{hashes_path}"
            
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.get(
                        url,
                        headers=self._headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        print(f"Torrin response for batch {i//batch_size}: {len(data)} entries", flush=True)
                        # Log first entry for debugging
                        if data:
                            first_key = list(data.keys())[0]
                            print(f"Sample response: {first_key[:16]}... -> {data[first_key]}", flush=True)
                        
                        # RD returns data keyed by hash (lowercase)
                        # IMPORTANT: Return result with ORIGINAL hash keys (not lowercase)
                        for h in batch:
                            hash_lower = h.lower()
                            if hash_lower in data and data[hash_lower]:
                                # Check if there's any RD array (indicates cached)
                                # Format: {"hash": {"rd": [...], ...}} or just empty object
                                entry = data[hash_lower]
                                if isinstance(entry, dict) and "rd" in entry and entry["rd"]:
                                    result[h] = CacheStatus.CACHED
                                    print(f"  {h[:16]}... -> CACHED", flush=True)
                                else:
                                    result[h] = CacheStatus.NOT_CACHED
                                    print(f"  {h[:16]}... -> NOT_CACHED (no rd array)", flush=True)
                            else:
                                result[h] = CacheStatus.NOT_CACHED
                                print(f"  {h[:16]}... -> NOT_CACHED (not in response)", flush=True)
                    else:
                        # On error, mark all as not cached
                        for h in batch:
                            result[h] = CacheStatus.NOT_CACHED
            except Exception as e:
                print(f"Torrin cache check error: {e}", flush=True)
                import traceback
                traceback.print_exc()
                for h in batch:
                    result[h] = CacheStatus.NOT_CACHED

        print(f"Torrin cache check result: {len(result)} entries, {sum(1 for v in result.values() if v == CacheStatus.CACHED)} cached", flush=True)
        return result



    async def add_magnet(self, magnet: str) -> str:
        # Use RealDebrid-compatible endpoint
        url = f"{self._rd_base}/torrents/addMagnet"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url,
                headers=self._headers,
                data={"magnet": magnet},
            )
            resp.raise_for_status()
            data = resp.json()
            # RD returns torrent ID
            return str(data["id"])

    async def list_files(self, torrent_id: str) -> list[dict]:
        # Use RealDebrid-compatible endpoint
        url = f"{self._rd_base}/torrents/info/{torrent_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            # Return files from RD-compatible response
            return data.get("files", [])

    async def list_user_torrents(self) -> list[dict]:
        """
        Attempts to list torrents present in the user's Torrin account.
        Returns a list of dicts; each dict should contain at least `hash` and
        optionally `filename` or `name` and `magnet` if available.
        This method is best-effort and returns an empty list on any failure.
        """
        try:
            url = f"{self._rd_base}/torrents"
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url,
                    headers=self._headers,
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()
                # RD returns a list of torrents
                if isinstance(data, list):
                    return data
                return []
        except Exception:
            return []

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        # Use RealDebrid-compatible endpoint
        # First get torrent info
        url = f"{self._rd_base}/torrents/info/{torrent_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                url,
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()

        # Check torrent status
        status = data.get("status", "")
        if status not in ["downloaded", "waiting_files_selection"]:
            raise RuntimeError(f"Torrent not ready on Torrin (status: {status})")

        # Get links
        links = data.get("links", [])
        if not links:
            raise RuntimeError("Torrent not ready on Torrin - no links available")

        # Select appropriate link
        idx = file_index if file_index is not None and file_index < len(links) else 0
        chosen_link = links[idx]

        # Unrestrict the link
        unrestrict_url = f"{self._rd_base}/unrestrict/link"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                unrestrict_url,
                headers=self._headers,
                data={"link": chosen_link},
            )
            resp.raise_for_status()
            unrestricted = resp.json()

        return ResolveResponse(
            playback_url=unrestricted["download"],
            file_name=unrestricted.get("filename"),
            provider="torrin",
        )
