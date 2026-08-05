"""
Stremio addon protocol routes.

Stremio addons are just HTTP endpoints returning specific JSON shapes:
  GET /manifest.json
  GET /stream/{type}/{id}.json

User-specific config (which debrid provider + API key to use) is passed as
a base64url-encoded JSON blob as the first path segment, e.g.:
  /<config>/manifest.json
  /<config>/stream/movie/tt1234567.json

This mirrors how Comet/MediaFusion/Torrentio let each user "install" the
addon with their own debrid credentials baked into their personal URL,
without the server needing to store any user accounts.
"""
import base64
import binascii
import json

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.debrid.factory import get_debrid_client
from app.models import CacheStatus, DebridProvider
from app.scrapers.aggregator import search_all

router = APIRouter(tags=["stremio"])
settings = get_settings()


def _manifest() -> dict:
    return {
        "id": settings.addon_id,
        "version": settings.addon_version,
        "name": settings.addon_name,
        "description": "Torrent search + debrid resolution addon for Stremio.",
        "resources": ["stream"],
        "types": ["movie", "series"],
        "idPrefixes": ["tt"],
        "catalogs": [],
        "behaviorHints": {"configurable": True, "configurationRequired": True},
    }


def _decode_config(config: str) -> dict:
    try:
        padded = config + "=" * (-len(config) % 4)
        raw = base64.urlsafe_b64decode(padded.encode())
        return json.loads(raw)
    except (ValueError, binascii.Error, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid addon configuration") from exc


@router.get("/manifest.json")
async def manifest_unconfigured():
    return _manifest()


@router.get("/{config}/manifest.json")
async def manifest_configured(config: str):
    return _manifest()


@router.get("/{config}/stream/{type}/{id}.json")
async def stream(config: str, type: str, id: str):
    cfg = _decode_config(config)
    provider_str = cfg.get("provider")
    api_key = cfg.get("api_key")
    if not provider_str or not api_key:
        raise HTTPException(status_code=400, detail="Missing provider or api_key in config")

    try:
        provider = DebridProvider(provider_str)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider_str}") from exc

    # id is an IMDb id, optionally with :season:episode for series
    imdb_id = id.split(":")[0]
    query = imdb_id  # Jackett/most indexers can search by IMDb id directly;
    # swap in a title-lookup step here (e.g. via Cinemeta) if you want
    # free-text queries instead.

    torrents = await search_all(query, imdb_id=imdb_id)
    if not torrents:
        return {"streams": []}

    client = get_debrid_client(provider, api_key)
    status_map = await client.check_cache([t.info_hash for t in torrents])

    streams = []
    for t in torrents:
        cached = status_map.get(t.info_hash) == CacheStatus.CACHED
        label_bits = [t.quality or "", f"👤{t.seeders}" if t.seeders else "", "⚡" if cached else ""]
        streams.append(
            {
                "name": f"{settings.addon_name} {'(cached)' if cached else ''}".strip(),
                "title": f"{t.title}\n{' '.join(b for b in label_bits if b)}",
                "infoHash": t.info_hash,
                "sources": [f"tracker:{t.info_hash}"],
                "behaviorHints": {"bingeGroup": f"{settings.addon_id}-{t.quality or 'unknown'}"},
            }
        )

    return {"streams": streams}
