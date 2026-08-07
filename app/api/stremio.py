import re

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.scrapers.aggregator import search_all
from app.debrid.factory import get_debrid_client
from app.models import DebridProvider, CacheStatus
from app.config_store import load_config
from app.filtering.sorting import sort_torrents
from app.filtering.validation import validate_torrent_title
from app.filtering.pipeline import FilterPipeline

router = APIRouter()

_CINEMETA_URL = "https://v3-cinemeta.strem.io/meta/{media_type}/{imdb_id}.json"


async def _resolve_metadata(media_type: str, imdb_id: str) -> tuple[str, int | None, list[str]]:
    """Resolve Stremio's IMDb ID to the title public indexers understand."""
    if media_type not in {"movie", "series"} or not re.fullmatch(r"tt\d+", imdb_id):
        raise HTTPException(400, "Unsupported media type or invalid IMDb ID")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_CINEMETA_URL.format(media_type=media_type, imdb_id=imdb_id))
            response.raise_for_status()
        meta = response.json().get("meta", {})
        title = meta.get("name")
        if not isinstance(title, str) or not title:
            raise ValueError("Cinemeta returned no title")

        year_match = re.search(r"(?:19|20)\d{2}", str(meta.get("year") or meta.get("releaseInfo") or ""))
        year = int(year_match.group()) if year_match else None
        raw_aliases = meta.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raw_aliases = []
        aliases = [value for value in [meta.get("originalName"), *raw_aliases] if isinstance(value, str)]
        return title, year, aliases
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Metadata lookup failed for {imdb_id}: {exc}", flush=True)
        raise HTTPException(502, "Unable to resolve requested media metadata") from exc


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


@router.get("/{config}/playback/{info_hash}")
async def playback(
    config: str,
    info_hash: str,
    file_index: int = Query(None, alias="fileIndex")
):
    """
    Playback endpoint - generates debrid streaming URL on demand.
    Called when user clicks play on a stream.
    """
    try:
        print("=== CAULDRON PLAYBACK REQUEST ===", flush=True)
        print(f"INFO_HASH: {info_hash}", flush=True)
        print(f"FILE_INDEX: {file_index}", flush=True)

        cfg = _decode_config(config)

        # Get debrid credentials
        provider_str, api_key = normalize_debrid(cfg)
        debrid_client = None

        if provider_str and api_key:
            try:
                provider = DebridProvider(provider_str)
                debrid_client = get_debrid_client(provider, api_key)
                print(f"Using debrid provider: {provider_str}", flush=True)
            except Exception as e:
                print(f"Error initializing debrid client: {e}", flush=True)
                raise HTTPException(500, "Debrid service not available")

        if not debrid_client:
            # Fallback to P2P streaming - return magnet link
            print("No debrid configured, falling back to P2P", flush=True)
            magnet = f"magnet:?xt=urn:btih:{info_hash}"
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=magnet)

        # Construct magnet for this info_hash
        magnet = f"magnet:?xt=urn:btih:{info_hash}"

        # Add to debrid and get playback link
        torrent_id = await debrid_client.add_magnet(magnet)
        playback_info = await debrid_client.get_playback_link(torrent_id, file_index)

        print(f"Generated playback URL: {playback_info.playback_url[:50]}...", flush=True)

        # Return redirect to the debrid URL
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=playback_info.playback_url)

    except HTTPException:
        raise
    except Exception as e:
        print(f"PLAYBACK ERROR: {repr(e)}", flush=True)
        raise HTTPException(500, str(e))


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
        else:
            print("No debrid credentials configured - using pure torrent mode", flush=True)

        parts = id.split(":")

        imdb_id = parts[0]

        season = None
        episode = None


        if type == "series" and len(parts) >= 3:
            season = parts[1]
            episode = parts[2]

        expected_title, expected_year, aka_titles = await _resolve_metadata(type, imdb_id)

        print(
            "SEARCHING:",
            expected_title,
            f"({imdb_id})",
            season,
            episode,
            flush=True
        )


        torrents = await search_all(
            query=expected_title,
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


        validated_torrents = []
        for torrent in torrents:
            valid, reason = validate_torrent_title(
                torrent.title, expected_title, expected_year, type, aka_titles
            )
            if valid:
                validated_torrents.append(torrent)
            else:
                print(f"Rejected unrelated torrent: {torrent.title[:80]} ({reason})", flush=True)
        torrents = validated_torrents
        print(f"After title validation: {len(torrents)} torrents", flush=True)


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
                # Log some cache statuses for debugging
                for info_hash, status in list(cache_status_map.items())[:5]:
                    print(f"  {info_hash[:16]}... -> {status}", flush=True)
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
                # f"e{e:02d}",  # Commented - matches wrong seasons
                # f"episode {e}",  # Commented - matches wrong seasons
                # f"episode.{e}",  # Commented - matches wrong seasons
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

        # Apply filtering pipeline (resolution limits, quality filters, etc.)
        pipeline = FilterPipeline(cfg)
        torrents = pipeline.apply(torrents)
        print(f"After filtering pipeline: {len(torrents)} torrents", flush=True)


        # Apply sorting based on user preferences
        sort_criteria = cfg.get("sort_criteria")
        if isinstance(sort_criteria, str):
            sort_criteria = sort_criteria.split(",") if sort_criteria else ["seeders", "resolution", "quality"]
        elif not sort_criteria:
            sort_criteria = ["seeders", "resolution", "quality"]
        
        sort_order = cfg.get("sort_order", "desc")
        allow_season_packs = cfg.get("allow_season_packs", False)
        
        torrents = sort_torrents(
            torrents,
            sort_criteria=sort_criteria,
            sort_order=sort_order,
            allow_season_packs=allow_season_packs,
            cache_status_map=cache_status_map if debrid_client else None
        )
        print(f"After sorting by {sort_criteria} {sort_order}: {len(torrents)} torrents", flush=True)


        output = []


        for torrent in torrents:

            # Determine stream name based on cache status and debrid configuration
            cache_status = cache_status_map.get(torrent.info_hash, CacheStatus.UNKNOWN)
            stream_name = "Cauldron"

            if debrid_client:
                if cache_status == CacheStatus.CACHED:
                    stream_name = "⚡ Cauldron (Cached)"
                elif cache_status == CacheStatus.NOT_CACHED:
                    stream_name = "⏳ Cauldron (uncached)"
                else:
                    stream_name = "⏳ Cauldron (uncached)"
            else:
                # No debrid configured - pure P2P
                stream_name = "Cauldron (P2P)"

            # Build stream URL
            if debrid_client:
                # Use playback endpoint for debrid streams
                from app.config import get_settings
                settings = get_settings()
                base_url = settings.addon_url.rstrip('/')
                stream_url = f"{base_url}/{config}/playback/{torrent.info_hash}"
                
                stream_data = {
                    "name": stream_name,
                    "title": torrent.title,
                    "url": stream_url,
                    "behaviorHints": {
                        "bingeGroup": "cauldron"
                    }
                }
            else:
                # Use magnet for P2P
                stream_data = {
                    "name": stream_name,
                    "title": torrent.title,
                    "infoHash": torrent.info_hash,
                    "sources": [f"magnet:{torrent.magnet}"],
                    "behaviorHints": {
                        "bingeGroup": "cauldron"
                    }
                }

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
