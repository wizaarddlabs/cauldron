"""
Cauldron Stremio addon routes.
"""

import base64
import binascii
import json

from fastapi import APIRouter, HTTPException, Request

from app.filtering.pipeline import FilterPipeline
from app.config import get_settings
from app.config_store import load_config
from app.debrid.factory import get_debrid_client
from app.models import CacheStatus, DebridProvider, TorrentResult
from app.scrapers.aggregator import search_all


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
        },
        "config": [
            {
                "key": "provider",
                "type": "select",
                "title": "Debrid Provider",
                "options": [
                    "torbox",
                    "realdebrid",
                    "premiumize"
                ]
            },
            {
                "key": "torbox_key",
                "type": "password",
                "title": "TorBox API Key"
            },
            {
                "key": "realdebrid_key",
                "type": "password",
                "title": "Real-Debrid API Key"
            },
            {
                "key": "premiumize_key",
                "type": "password",
                "title": "Premiumize API Key"
            },
            {
                "key": "addon_name",
                "type": "text",
                "title": "Addon Name"
            },
            {
                "key": "cached_only",
                "type": "checkbox",
                "title": "Cached Only"
            },
            {
                "key": "scrape_debrid",
                "type": "checkbox",
                "title": "Scrape Debrid Account Torrents"
            }
        ]
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



def _parse_bool(value):

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value).lower() in {
        "1",
        "true",
        "yes",
        "on",
        "checked",
        "y",
        "t"
    }


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
async def manifest(request: Request):

    host = request.headers.get(
        "host",
        "localhost:8000"
    )

    scheme = request.headers.get(
        "x-forwarded-proto",
        "http"
    )

    base_url = f"{scheme}://{host}"

    return _manifest(base_url)


@router.get("/{config}/manifest.json")
async def manifest_configured(request: Request, config:str):

    host = request.headers.get(
        "host",
        "localhost:8000"
    )

    scheme = request.headers.get(
        "x-forwarded-proto",
        "http"
    )

    base_url = f"{scheme}://{host}"

    return _manifest(base_url)


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

    # Optionally include torrents from the user's debrid account
    if cfg.get("scrape_debrid"):

        try:
            client = get_debrid_client(provider, api_key)
            user_items = await client.list_user_torrents()
            user_torrents: list[TorrentResult] = []

            for item in user_items:

                h = item.get('hash') or item.get('info_hash') or item.get('id')

                if not h:
                    continue

                title = item.get('filename') or item.get('name') or f"Debrid {h[:8]}"

                magnet = item.get('magnet') or ''

                size = item.get('size') or item.get('size_bytes') or item.get('filesize')

                try:
                    size_bytes = int(size) if size else None
                except Exception:
                    size_bytes = None

                user_torrents.append(
                    TorrentResult(
                        title=title,
                        info_hash=h,
                        magnet=magnet,
                        size_bytes=size_bytes,
                        seeders=None,
                        source='debrid-account'
                    )
                )

            # Prepend user torrents so they are considered first
            torrents = user_torrents + torrents

        except Exception:
            # best-effort — ignore failures to list account torrents
            pass

    # Apply filtering pipeline using UI config
    pipeline = FilterPipeline(cfg)
    torrents = pipeline.apply(torrents)

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

    cached_only = _parse_bool(
        cfg.get("cached_only")
    )

    async def _build_cached_debrid_streams():
        streams = []

        for t in torrents:
            if status_map.get(t.info_hash) != CacheStatus.CACHED:
                continue

            magnet = (
                t.magnet
                if t.magnet
                else f"magnet:?xt=urn:btih:{t.info_hash}"
            )

            try:
                torrent_id = await client.add_magnet(magnet)
                playback = await client.get_playback_link(
                    torrent_id,
                    None,
                )

            except Exception:
                continue

            streams.append(
                {
                    "name":
                        f"🧙 Cauldron {provider.value.capitalize()} Cached",

                    "title":
                        t.title,

                    "infoHash":
                        t.info_hash,

                    "stream_url":
                        playback.playback_url,

                    "url":
                        playback.playback_url,

                    "sources":
                        [
                            f"tracker:{t.info_hash}"
                        ],

                    "provider":
                        str(playback.provider)
                }
            )

        return streams

    output = []

    if not cached_only:
        for t in torrents:
            output.append(
                {
                    "name":
                        f"🧙 Cauldron {'⚡ Cached' if status_map.get(t.info_hash) == CacheStatus.CACHED else ''}",

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

    output.extend(
        await _build_cached_debrid_streams()
    )

    return {
        "streams": output
    }
