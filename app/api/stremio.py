"""
Cauldron Stremio addon routes.
"""

import base64
import binascii
import json

from fastapi import APIRouter, HTTPException, Request

from app.filtering.pipeline import FilterPipeline
from app.filtering.sorting import sort_torrents
from app.config import get_settings
from app.config_store import load_config
from app.debrid.factory import get_debrid_client
from app.models import CacheStatus, DebridProvider
from app.scrapers.aggregator import search_all
from app.ranking.stream_titles import build_stream_name


router = APIRouter(tags=["stremio"])

settings = get_settings()


def _manifest(base_url: str):

    return {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": "Cauldron torrent + debrid addon",

        "logo":
            f"{base_url.rstrip('/')}/static/cauldron.png",

        "resources": [
            "stream"
        ],

        "types": [
            "movie",
            "series"
        ],

        "idPrefixes": [
            "tt"
        ],

        "catalogs": [],

        "behaviorHints": {
            "configurable": True
        }
    }



def _decode_config(config):

    try:

        stored = load_config(config)

        if stored:
            return stored

    except Exception:
        pass


    try:

        padded = config + "=" * (-len(config) % 4)

        raw = base64.urlsafe_b64decode(
            padded.encode()
        )

        return json.loads(raw)


    except (
        ValueError,
        binascii.Error,
        json.JSONDecodeError
    ):

        raise HTTPException(
            400,
            "Invalid config"
        )



def normalize_debrid(cfg):

    if cfg.get("provider") and cfg.get("api_key"):

        return (
            cfg["provider"],
            cfg["api_key"]
        )


    if cfg.get("torbox_key"):

        return (
            "torbox",
            cfg["torbox_key"]
        )


    if cfg.get("realdebrid_key"):

        return (
            "realdebrid",
            cfg["realdebrid_key"]
        )


    if cfg.get("premiumize_key"):

        return (
            "premiumize",
            cfg["premiumize_key"]
        )


    raise HTTPException(
        400,
        "Missing debrid credentials"
    )



@router.get("/manifest.json")
async def manifest(request: Request):

    host = request.headers.get(
        "host",
        "localhost:8000"
    )

    scheme = request.headers.get(
        "x-forwarded-proto",
        "http"
    )

    return _manifest(
        f"{scheme}://{host}"
    )



@router.get("/{config}/manifest.json")
async def manifest_configured(
    request: Request,
    config: str
):

    host = request.headers.get(
        "host",
        "localhost:8000"
    )

    scheme = request.headers.get(
        "x-forwarded-proto",
        "http"
    )

    return _manifest(
        f"{scheme}://{host}"
    )



@router.get("/{config}/stream/{type}/{id}.json")
async def stream(
    config: str,
    type: str,
    id: str
):

    try:

        cfg = _decode_config(config)


        provider_str, api_key = normalize_debrid(
            cfg
        )


        provider = DebridProvider(
            provider_str
        )


        #
        # Parse Stremio ID
        #
        # movie:
        # tt0133093
        #
        # series:
        # tt0944947:1:1
        #

        parts = id.split(":")

        imdb_id = parts[0]


        season = None
        episode = None


        if type == "series":

            if len(parts) >= 3:

                season = parts[1]
                episode = parts[2]



        #
        # Search torrents
        #
        # Keep compatible with existing scraper
        #

        torrents = await search_all(
            imdb_id,
            imdb_id=imdb_id
        )


        if not torrents:

            return {
                "streams":[]
            }



        #
        # Series filtering
        #

        if type == "series" and season and episode:

            filtered = []

            for torrent in torrents:

                title = torrent.title.lower()

                if (
                    f"s{int(season):02d}e{int(episode):02d}"
                    in title
                    or
                    f"s{season}e{episode}"
                    in title
                ):

                    filtered.append(
                        torrent
                    )


            torrents = filtered



        if not torrents:

            return {
                "streams":[]
            }



        #
        # User filters
        #

        torrents = FilterPipeline(cfg).apply(
            torrents
        )



        #
        # Ranking
        #

        torrents = sort_torrents(
            torrents
        )


        if not torrents:

            return {
                "streams":[]
            }



        client = get_debrid_client(
            provider,
            api_key
        )



        status_map = await client.check_cache(
            [
                t.info_hash
                for t in torrents
            ]
        )



        output = []



        for torrent in torrents:


            cached = (
                status_map.get(
                    torrent.info_hash
                )
                == CacheStatus.CACHED
            )


            if not cached:
                continue



            output.append(
                {

                    "name":
                        build_stream_name(
                            torrent.title
                        ),


                    "title":
                        torrent.title,


                    "infoHash":
                        torrent.info_hash,


                    "sources":
                        [
                            f"tracker:{torrent.info_hash}"
                        ],


                    "behaviorHints":
                        {
                            "bingeGroup":
                                "cauldron"
                        }

                }
            )



        return {
            "streams": output
        }


    except Exception as e:

        print(
            "CAULDRON STREAM ERROR:",
            repr(e),
            flush=True
        )

        raise HTTPException(
            500,
            str(e)
        )