"""Turn ranked torrent results into Stremio stream objects."""

import logging

from app.logging_utils import mask_config_id
from app.models import CacheStatus

logger = logging.getLogger(__name__)


def cache_status_label(status):
    if status == CacheStatus.CACHED:
        return "⚡ Cached"

    if status == CacheStatus.NOT_CACHED:
        return "⏳ Uncached"

    return "❔ Unknown"


def build_stream(
    torrent,
    *,
    cache_status_map,
    has_debrid: bool,
    base_url: str,
    config: str,
    provider: str | None = None,
    provider_label: str | None = None,
) -> dict | None:
    """
    Build one Stremio stream entry, or ``None`` if the torrent is unusable.

    With a debrid provider the stream points at Cauldron's playback
    endpoint; otherwise it is a plain P2P infoHash stream.

    ``provider`` routes playback through that specific provider (configs
    with several providers); ``cache_status_map`` must then be that
    provider's map. ``provider_label`` adds the provider's name to the
    stream so users can tell them apart.
    """

    info_hash = str(
        getattr(
            torrent,
            "info_hash",
            "",
        )
    ).lower()

    if not info_hash:
        logger.warning(
            "Skipping torrent without "
            "info hash: %s",
            getattr(
                torrent,
                "title",
                "unknown",
            ),
        )

        return None

    cache_status = (
        cache_status_map.get(
            info_hash,
            CacheStatus.UNKNOWN,
        )
    )

    cache_label = (
        cache_status_label(
            cache_status
        )
    )

    quality = getattr(
        torrent,
        "quality",
        None,
    )

    indexer = getattr(
        torrent,
        "indexer",
        None,
    )

    seeders = getattr(
        torrent,
        "seeders",
        None,
    )

    size_bytes = getattr(
        torrent,
        "size_bytes",
        None,
    )

    # -------------------------------------------------
    # STREAM NAME
    # -------------------------------------------------

    name_parts = [
        "🧙 Cauldron"
    ]

    if indexer:
        name_parts.append(
            str(indexer)
        )

    if quality:
        name_parts.append(
            str(quality)
        )

    if has_debrid:
        if provider_label:
            name_parts.append(
                provider_label
            )

        name_parts.append(
            cache_label
        )
    else:
        name_parts.append(
            "P2P"
        )

    stream_name = (
        " • ".join(
            name_parts
        )
    )

    # -------------------------------------------------
    # STREAM TITLE
    # -------------------------------------------------

    title_parts = [
        str(
            getattr(
                torrent,
                "title",
                "Unknown",
            )
        )
    ]

    if quality:
        title_parts.append(
            f"Quality: {quality}"
        )

    if seeders is not None:
        title_parts.append(
            f"Seeds: {seeders}"
        )

    if size_bytes:
        try:
            size_gb = (
                float(size_bytes)
                / (1024 ** 3)
            )

            if size_gb >= 1:
                title_parts.append(
                    f"Size: "
                    f"{size_gb:.2f} GB"
                )

            else:
                size_mb = (
                    float(size_bytes)
                    / (1024 ** 2)
                )

                title_parts.append(
                    f"Size: "
                    f"{size_mb:.0f} MB"
                )

        except (
            TypeError,
            ValueError,
        ):
            pass

    if has_debrid:
        title_parts.append(
            f"Cache: {cache_label}"
            + (f" ({provider_label})" if provider_label else "")
        )

    # -------------------------------------------------
    # PLAYBACK URL
    # -------------------------------------------------

    if has_debrid:
        stream_url = (
            f"{base_url}/{config}/playback/{provider}/{info_hash}"
            if provider
            else f"{base_url}/{config}/playback/{info_hash}"
        )

        stream_data = {
            "name": stream_name,
            "title": "\n".join(
                title_parts
            ),
            "url": stream_url,
            "behaviorHints": {
                # Per provider, so Stremio's "next episode" keeps using the
                # same debrid service.
                "bingeGroup": (
                    f"cauldron-{provider}" if provider else "cauldron"
                ),
            },
        }

        logger.debug(
            "Playback URL: %s",
            stream_url.replace(
                config,
                mask_config_id(config),
            ),
        )

    else:
        magnet = getattr(
            torrent,
            "magnet",
            None,
        )

        stream_data = {
            "name": stream_name,
            "title": "\n".join(
                title_parts
            ),
            "infoHash": info_hash,
            "sources": (
                [magnet]
                if magnet
                else []
            ),
            "behaviorHints": {
                "bingeGroup": (
                    "cauldron"
                ),
            },
        }

    return stream_data
