"""
Cauldron Stremio addon routes.
"""

import base64
import binascii
import json

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.config_store import load_config
from app.debrid.factory import get_debrid_client
from app.models import CacheStatus, DebridProvider
from app.scrapers.aggregator import search_all


router = APIRouter(tags=["stremio"])

settings = get_settings()


def _manifest():

    return {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": "Cauldron torrent + debrid addon",
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
        "catalogs": []
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

    """
    Converts Cauldron UI config
    into internal provider/api_key format.
    """

    if cfg.get("provider") and cfg.get("api_key"):
        return (
            cfg["provider"],
            cfg["api_key"]
        )


    if cfg.get("realdebrid_key"):

        return (
            "realdebrid",
            cfg["realdebrid_key"]
        )


    if cfg.get("torbox_key"):

        return (
            "torbox",
            cfg["torbox_key"]
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
async def manifest():

    return _manifest()



@router.get("/{config}/manifest.json")
async def manifest_configured(config:str):

    return _manifest()



@router.get(
    "/{config}/stream/{type}/{id}.json"
)
async def stream(
    config:str,
    type:str,
    id:str
):

    cfg = _decode_config(config)


    provider_str, api_key = normalize_debrid(cfg)


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


    output=[]


    for t in torrents:

        cached = (
            status_map.get(t.info_hash)
            ==
            CacheStatus.CACHED
        )


        output.append(
            {
                "name":
                    f"🧙 Cauldron {'⚡ Cached' if cached else ''}",

                "title":
                    t.title,

                "infoHash":
                    t.info_hash,

                "sources":
                    [
                        f"tracker:{t.info_hash}"
                    ]
            }
        )


    return {
        "streams":output
    }
