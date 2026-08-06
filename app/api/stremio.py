from fastapi import APIRouter, HTTPException

from app.scrapers.aggregator import search_all
from app.debrid.factory import get_debrid_client
from app.models import DebridProvider, CacheStatus
from app.config_store import load_config

router = APIRouter()


def _decode_config(config: str):
    """
    Try to load config from database first, otherwise keep compatibility
    with Stremio config URLs.
    """
    try:
        stored = load_config(config)
        if stored:
            return stored
    except Exception:
        pass

    # Fallback for compatibility
    return {
        "config": config
    }


def normalize_debrid(cfg):
    """
    Normalize debrid credentials from config to provider and api_key.
    """
    if cfg.get("provider") and cfg.get("api_key"):
        return cfg["provider"], cfg["api_key"]

    if cfg.get("torbox_key"):
        return "torbox", cfg["torbox_key"]

    if cfg.get("realdebrid_key"):
        return "realdebrid", cfg["realdebrid_key"]

    if cfg.get("alldebrid_key"):
        return "alldebrid", cfg["alldebrid_key"]

    if cfg.get("premiumize_key"):
        return "premiumize", cfg["premiumize_key"]

    return None, None


@router.get("/{config}/stream/{type}/{id}.json")
async def stream(
    config: str,
    type: str,
    id: str
):

    try:

        print("=== CAULDRON STREAM REQUEST ===", flush=True)
        print("TYPE:", type, flush=True)
        print("ID:", id, flush=True)

        cfg = _decode_config(config)

        # Get debrid credentials
        provider_str, api_key = normalize_debrid(cfg)
        debrid_client = None
        cache_status_map = {}

        if provider_str and api_key:
            try:
                provider = DebridProvider(provider_str)
                debrid_client = get_debrid_client(provider, api_key)
                print(f"Using debrid provider: {provider_str}", flush=True)
            except Exception as e:
                print(f"Error initializing debrid client: {e}", flush=True)

        parts = id.split(":")

        imdb_id = parts[0]

        season = None
        episode = None


        if type == "series" and len(parts) >= 3:
            season = parts[1]
            episode = parts[2]


        print(
            "SEARCHING:",
            imdb_id,
            season,
            episode,
            flush=True
        )


        torrents = await search_all(
            query=imdb_id,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            media_type=type
        )


        print(
            "FOUND TORRENTS:",
            len(torrents),
            flush=True
        )


        if not torrents:
            return {
                "streams": []
            }


        # Check cache status if debrid is available
        if debrid_client:
            try:
                info_hashes = [t.info_hash for t in torrents]
                cache_status_map = await debrid_client.check_cache(info_hashes)
                print(f"Cache check completed for {len(info_hashes)} torrents", flush=True)
            except Exception as e:
                print(f"Error checking cache: {e}", flush=True)


        # Better episode matching
        if type == "series" and season and episode:

            filtered = []

            s = int(season)
            e = int(episode)

            patterns = [
                f"s{s:02d}e{e:02d}",
                f"s{s}e{e}",
                f"{s}x{e:02d}",
                f"e{e:02d}",
                f"episode {e}",
                f"episode.{e}",
            ]


            for torrent in torrents:

                title = torrent.title.lower()


                if any(
                    pattern.lower() in title
                    for pattern in patterns
                ):
                    filtered.append(torrent)


            torrents = filtered


            print(
                "AFTER EP FILTER:",
                len(torrents),
                flush=True
            )


        # Filter by cached only if enabled
        cached_only = cfg.get("cached_only", False)
        if cached_only and debrid_client:
            torrents = [
                t for t in torrents
                if cache_status_map.get(t.info_hash) == CacheStatus.CACHED
            ]
            print(f"After cached_only filter: {len(torrents)} torrents", flush=True)


        output = []


        for torrent in torrents[:25]:

            # Determine stream name based on cache status
            cache_status = cache_status_map.get(torrent.info_hash, CacheStatus.UNKNOWN)
            stream_name = "Cauldron"

            if debrid_client:
                if cache_status == CacheStatus.CACHED:
                    stream_name = "⚡ Cauldron (Cached)"
                elif cache_status == CacheStatus.NOT_CACHED:
                    stream_name = "⏳ Cauldron (Debrid)"
                else:
                    stream_name = "⏳ Cauldron (Debrid)"

            stream_data = {
                "name": stream_name,
                "title": torrent.title,
                "infoHash": torrent.info_hash,
                "sources": [f"magnet:{torrent.magnet}"],
                "behaviorHints": {
                    "bingeGroup": "cauldron"
                }
            }

            # Add cache status to behavior hints for Stremio
            if debrid_client and cache_status == CacheStatus.CACHED:
                stream_data["behaviorHints"]["notWatched"] = False

            output.append(stream_data)


        print(
            "RETURNING STREAMS:",
            len(output),
            flush=True
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
