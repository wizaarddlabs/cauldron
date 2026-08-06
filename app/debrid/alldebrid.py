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
AGENT = "torrentio-debrid"


class AllDebridClient(DebridClient):
    provider_name = "alldebrid"

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._base = settings.alldebrid_api_base
        self._params = {"agent": AGENT, "apikey": api_key}

    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        if not info_hashes:
            return {}
        url = f"{self._base}/magnet/instant"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                params={**self._params, "magnets[]": info_hashes},
            )
            resp.raise_for_status()
            data = resp.json()

        result: dict[str, CacheStatus] = {}
        magnets = data.get("data", {}).get("magnets", [])
        by_hash = {m.get("hash", "").lower(): m for m in magnets}
        for h in info_hashes:
            m = by_hash.get(h.lower())
            cached = bool(m) and m.get("instant") is True
            result[h] = CacheStatus.CACHED if cached else CacheStatus.NOT_CACHED
        return result

    async def add_magnet(self, magnet: str) -> str:
        url = f"{self._base}/magnet/upload"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={**self._params, "magnets[]": [magnet]})
            resp.raise_for_status()
            data = resp.json()
            magnet_info = data["data"]["magnets"][0]
            return str(magnet_info["id"])

    async def list_files(self, torrent_id: str) -> list[dict]:
        url = f"{self._base}/magnet/status"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={**self._params, "id": torrent_id})
            resp.raise_for_status()
            data = resp.json()
            magnet = data.get("data", {}).get("magnets", {})
            return magnet.get("links", [])

    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        try:
            files = await self.list_files(torrent_id)
            if not files:
                raise RuntimeError("Torrent not yet ready on AllDebrid (still downloading?)")

            idx = file_index if file_index is not None and file_index < len(files) else 0
            chosen = files[idx]
            link = chosen.get("link")

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self._base}/link/unlock", params={**self._params, "link": link}
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
                resp = await client.get(url, params={**self._params})
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
