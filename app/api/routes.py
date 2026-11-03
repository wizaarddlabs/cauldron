"""
Standalone REST API: search across scrapers, check debrid cache status,
resolve a magnet to a playable link, and manage ranking preferences.
"""

from fastapi import APIRouter, Header, HTTPException, Query
import hashlib
import json
import logging


from app.cache.store import cache_get, cache_set, get_cache_stats
from app.config import get_settings
from app.debrid.factory import get_debrid_client

from app.models import (
    CacheStatus,
    AvailabilityRequest,
    DebridProvider,
    ResolveRequest,
    ResolveResponse,
    StreamCandidate,
    TorrentResult,
)

from app.scrapers.aggregator import search_all

from app.ranking.preferences import RankingPreferences
from app.ranking.store import (
    load_preferences,
    save_preferences,
)
from app.security import require_admin_api_key


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["api"],
)

settings = get_settings()


def _search_cache_key(
    q: str,
    imdb_id: str | None,
    season: str | None,
    episode: str | None,
    media_type: str | None,
    preferences: RankingPreferences,
) -> str:
    ranking_inputs = json.dumps(
        {
            "preferred_languages": preferences.preferred_languages,
            "seeder_weight": preferences.seeder_weight,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    ranking_fingerprint = hashlib.sha256(
        ranking_inputs.encode("utf-8")
    ).hexdigest()

    return (
        f"search:{q}:{imdb_id or ''}:{season or ''}:{episode or ''}:"
        f"{media_type or ''}:{ranking_fingerprint}"
    )


@router.get(
    "/search",
    response_model=list[TorrentResult],
)
async def search(
    q: str = Query(
        ...,
        description="Free-text search query",
    ),
    imdb_id: str | None = Query(
        default=None,
    ),
    season: str | None = Query(
        default=None,
    ),
    episode: str | None = Query(
        default=None,
    ),
    media_type: str | None = Query(
        default=None,
    ),
):

    preferences = load_preferences()
    cache_key = _search_cache_key(
        q,
        imdb_id,
        season,
        episode,
        media_type,
        preferences,
    )

    cached = await cache_get(cache_key)

    if cached is not None:
        return cached




    results = await search_all(
        q,
        imdb_id=imdb_id,
        season=season,
        episode=episode,
        media_type=media_type,
        preferences=preferences,
    )


    payload = [
        r.model_dump()
        for r in results
    ]


    await cache_set(
        cache_key,
        payload,
        settings.cache_ttl_search,
    )


    return results



@router.get(
    "/settings/ranking",
    response_model=RankingPreferences,
)
async def get_ranking_settings():

    return load_preferences()



@router.post(
    "/settings/ranking",
    response_model=RankingPreferences,
)
async def update_ranking_settings(
    preferences: RankingPreferences,
    x_admin_api_key: str | None = Header(default=None),
):
    require_admin_api_key(x_admin_api_key)

    save_preferences(
        preferences
    )

    return preferences



async def _availability(
    q: str,
    provider: DebridProvider,
    api_key: str,
    imdb_id: str | None = None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
):

    torrents = await search_all(
        q,
        imdb_id=imdb_id,
        season=season,
        episode=episode,
        media_type=media_type,
        preferences=load_preferences(),
    )

    if not torrents:
        return []

    client = get_debrid_client(
        provider,
        api_key,
    )

    cache_key = (
        f"avail:{provider}:{q}:{season or ''}:{episode or ''}:{media_type or ''}:"
        f"{','.join(t.info_hash for t in torrents)}"
    )

    cached_map = await cache_get(cache_key)

    if cached_map is None:
        try:
            status_map = await client.check_cache(
                [torrent.info_hash for torrent in torrents]
            )
        except Exception as exc:
            logger.warning(
                "Debrid availability check failed for %s (%s)",
                provider.value,
                type(exc).__name__,
            )
            raise HTTPException(
                status_code=502,
                detail="Debrid provider availability check failed",
            ) from exc

        cached_map = {
            key: value.value
            for key, value in status_map.items()
        }

        await cache_set(
            cache_key,
            cached_map,
            settings.cache_ttl_availability,
        )

    return [
        StreamCandidate(
            torrent=torrent,
            provider=provider,
            cache_status=CacheStatus(
                cached_map.get(
                    torrent.info_hash,
                    CacheStatus.UNKNOWN.value,
                )
            ),
        )
        for torrent in torrents
    ]


@router.post(
    "/availability",
    response_model=list[StreamCandidate],
)
async def availability_post(request: AvailabilityRequest):
    return await _availability(**request.model_dump())


@router.get(
    "/availability",
    response_model=list[StreamCandidate],
    deprecated=True,
)
async def availability(
    q: str = Query(...),
    provider: DebridProvider = Query(...),
    api_key: str = Query(
        ...,
        description="Your debrid provider API key",
    ),
    imdb_id: str | None = Query(
        default=None,
    ),
    season: str | None = Query(
        default=None,
    ),
    episode: str | None = Query(
        default=None,
    ),
    media_type: str | None = Query(
        default=None,
    ),
):
    return await _availability(
        q,
        provider,
        api_key,
        imdb_id=imdb_id,
        season=season,
        episode=episode,
        media_type=media_type,
    )



@router.post(
    "/resolve",
    response_model=ResolveResponse,
)
async def resolve(
    req: ResolveRequest,
):
    try:
        client = get_debrid_client(
            req.provider,
            req.api_key,
        )
        torrent_id = await client.add_magnet(
            req.magnet
        )

        return await client.get_playback_link(
            torrent_id,
            req.file_index,
        )
    except Exception as exc:
        logger.warning(
            "Debrid resolve failed for %s (%s)",
            req.provider.value,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Debrid provider resolve failed",
        ) from exc


@router.get("/cache/stats")
async def cache_stats():
    """Return cache hit/miss statistics for monitoring."""
    return get_cache_stats()
