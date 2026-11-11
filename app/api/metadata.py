"""Resolve Stremio IDs to title/year/aliases via Cinemeta."""

import logging

from fastapi import HTTPException

from app.http_client import http_session

logger = logging.getLogger(__name__)

CINEMETA_URL = (
    "https://v3-cinemeta.strem.io/meta/{type}/{id}.json"
)

# =========================================================
# MEDIA RESOLUTION
# =========================================================


async def resolve_media(type_: str, id_: str):
    imdb_id = id_
    season = None
    episode = None

    if type_ == "series" and ":" in id_:
        parts = id_.split(":")

        imdb_id = parts[0]

        if len(parts) >= 2:
            try:
                season = int(parts[1])
            except ValueError:
                season = None

        if len(parts) >= 3:
            try:
                episode = int(parts[2])
            except ValueError:
                episode = None

    url = CINEMETA_URL.format(
        type="movie" if type_ == "movie" else "series",
        id=imdb_id,
    )

    try:
        async with http_session(
            timeout=15
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

    except Exception as exc:
        logger.exception(
            "Failed to resolve Cinemeta metadata"
        )

        raise HTTPException(
            status_code=502,
            detail=f"Unable to resolve metadata: {exc}",
        ) from exc

    meta = data.get("meta") or {}

    title = meta.get("name") or meta.get("title")

    if not title:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve title for {imdb_id}",
        )

    year = meta.get("year")

    try:
        year = int(year) if year else None
    except (TypeError, ValueError):
        year = None

    aliases = meta.get("aliases") or []

    logger.info("=== RESOLVED MEDIA ===")
    logger.info("Type: %s", type_)
    logger.info("IMDb: %s", imdb_id)
    logger.info("Title: %s", title)
    logger.info("Year: %s", year)
    logger.info("Aliases: %s", aliases)
    logger.info("Season: %s", season)
    logger.info("Episode: %s", episode)

    return {
        "type": type_,
        "imdb_id": imdb_id,
        "title": title,
        "year": year,
        "aliases": aliases,
        "season": season,
        "episode": episode,
    }
