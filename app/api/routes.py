"""
Standalone REST API: search across scrapers, check debrid cache status,
resolve a magnet to a playable link, and manage ranking preferences.
"""

from fastapi import APIRouter, HTTPException, Query

from app.cache.store import cache_get, cache_set
from app.config import get_settings
from app.debrid.factory import get_debrid_client

from app.models import (
    CacheStatus,
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


router = APIRouter(
    prefix="/api",
    tags=["api"],
)

settings = get_settings()


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

    cache_key = f"search:{q}:{imdb_id or ''}:{season or ''}:{episode or ''}:{media_type or ''}"

    cached = await cache_get(cache_key)

    if cached is not None:
        return cached


    preferences = load_preferences()


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
):

    save_preferences(
        preferences
    )

    return preferences



@router.get(
    "/availability",
    response_model=list[StreamCandidate],
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

    print(f"Cache check for {len(torrents)} torrents", flush=True)


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


    cached_map = await cache_get(
        cache_key
    )


    if cached_map is None:

        status_map = await client.check_cache(
            [
                t.info_hash
                for t in torrents
            ]
        )


        cached_map = {
            k: v.value
            for k, v in status_map.items()
        }


        await cache_set(
            cache_key,
            cached_map,
            settings.cache_ttl_availability,
        )


    return [
        StreamCandidate(
            torrent=t,
            provider=provider,
            cache_status=CacheStatus(
                cached_map.get(
                    t.info_hash,
                    CacheStatus.UNKNOWN.value,
                )
            ),
        )
        for t in torrents
    ]



@router.post(
    "/resolve",
    response_model=ResolveResponse,
)
async def resolve(
    req: ResolveRequest,
):

    client = get_debrid_client(
        req.provider,
        req.api_key,
    )

    try:

        torrent_id = await client.add_magnet(
            req.magnet
        )


        return await client.get_playback_link(
            torrent_id,
            req.file_index,
        )


    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc
