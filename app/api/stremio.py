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
        "logo": f"{base_url.rstrip('/')}/static/cauldron.png",

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

    cfg = _decode_config(config)


    provider_str, api_key = normalize_debrid(
        cfg
    )


    try:

        provider = DebridProvider(
            provider_str
        )

    except Exception:

        raise HTTPException(
            400,
            "Invalid provider"
        )


    imdb_id = id.split(":")[0]


    torrents = await search_all(
        imdb_id,
        imdb_id=imdb_id
    )


    if not torrents:

        return {
            "streams": []
        }



    #
    # Apply user filters
    #

    torrents = FilterPipeline(cfg).apply(
        torrents
    )



    #
    # Sort by quality/ranking
    #

    torrents = sort_torrents(
        torrents
    )


    if not torrents:

        return {
            "streams": []
        }



    client = get_debrid_client(
        provider,
        api_key
    )



    #
    # Check instant cache
    #

    status_map = await client.check_cache(
        [
            t.info_hash
            for t in torrents
        ]
    )



    output = []



    for t in torrents:


        cached = (
            status_map.get(t.info_hash)
            == CacheStatus.CACHED
        )


        #
        # Cauldron only shows instant streams
        #

        if not cached:
            continue



        output.append(
            {

                "name":
                    build_stream_name(
                        t.title
                    ),


                "title":
                    t.title,


                #
                # Stremio compatible torrent metadata
                #

                "infoHash":
                    t.info_hash,


                "sources":
                    [
                        f"tracker:{t.info_hash}"
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