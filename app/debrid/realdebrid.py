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

        self._headers = {
            "Authorization": f"Bearer {api_key}"
        }


    async def check_cache(
        self,
        info_hashes: list[str]
    ) -> dict[str, CacheStatus]:

        if not info_hashes:
            return {}

        result = {}

        batch_size = 3

        async with httpx.AsyncClient(timeout=15) as client:

            for i in range(0, len(info_hashes), batch_size):

                batch = info_hashes[i:i + batch_size]

                hashes_path = "/".join(
                    h.lower()
                    for h in batch
                )

                url = (
                    f"{self._base}"
                    f"/torrents/instantAvailability/"
                    f"{hashes_path}"
                )

                try:
                    resp = await client.get(
                        url,
                        headers=self._headers
                    )

                    # RD disabled this endpoint. Treat it as no cache.
                    if resp.status_code != 200:
                        for h in batch:
                            result[h] = CacheStatus.NOT_CACHED
                        continue


                    data = resp.json()

                    for h in batch:

                        entry = (
                            data.get(h.lower())
                            or data.get(h.upper())
                        )

                        if entry:
                            result[h] = CacheStatus.CACHED
                        else:
                            result[h] = CacheStatus.NOT_CACHED


                except Exception:

                    for h in batch:
                        result[h] = CacheStatus.NOT_CACHED


        return result



    async def add_magnet(
        self,
        magnet: str
    ) -> str:

        url = f"{self._base}/torrents/addMagnet"

        async with httpx.AsyncClient(timeout=15) as client:

            resp = await client.post(
                url,
                headers=self._headers,
                data={
                    "magnet": magnet
                }
            )

            resp.raise_for_status()

            torrent_id = resp.json()["id"]


            select_url = (
                f"{self._base}"
                f"/torrents/selectFiles/"
                f"{torrent_id}"
            )


            await client.post(
                select_url,
                headers=self._headers,
                data={
                    "files": "all"
                }
            )


        return torrent_id



    async def list_files(
        self,
        torrent_id: str
    ) -> list[dict]:

        url = (
            f"{self._base}"
            f"/torrents/info/"
            f"{torrent_id}"
        )

        async with httpx.AsyncClient(timeout=15) as client:

            resp = await client.get(
                url,
                headers=self._headers
            )

            resp.raise_for_status()

            return resp.json().get(
                "files",
                []
            )



    async def get_playback_link(
        self,
        torrent_id: str,
        file_index: Optional[int] = None
    ) -> ResolveResponse:


        async with httpx.AsyncClient(timeout=15) as client:

            info_resp = await client.get(
                f"{self._base}/torrents/info/{torrent_id}",
                headers=self._headers
            )

            info_resp.raise_for_status()

            info = info_resp.json()

            links = info.get(
                "links",
                []
            )


            if not links:
                raise RuntimeError(
                    "Torrent not ready on Real-Debrid"
                )


            idx = (
                file_index
                if file_index is not None
                and file_index < len(links)
                else 0
            )


            restricted_link = links[idx]


            unrestrict_resp = await client.post(
                f"{self._base}/unrestrict/link",
                headers=self._headers,
                data={
                    "link": restricted_link
                }
            )


            unrestrict_resp.raise_for_status()

            unrestricted = unrestrict_resp.json()


        return ResolveResponse(
            playback_url=unrestricted["download"],
            file_name=unrestricted.get("filename"),
            provider="realdebrid"
        )
