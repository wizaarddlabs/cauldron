"""
Cauldron torrent sorting.

The user's sort_criteria list is authoritative.

Example:

    ["cached", "resolution", "seeders", "quality", "size"]

means:

    1. Cached before uncached
    2. Higher resolution first
    3. More seeders first
    4. Higher quality first
    5. Larger size first

The order of sort_criteria determines priority.
"""

from typing import List

from app.models import TorrentResult


# ---------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------

def _normalize_criterion(value: str) -> str:
    """
    Normalize UI/API criterion names.

    Accepts variants such as:

        cache
        cached
        cache_status
        cache status
        Cache Status

    and normalizes them to:

        cached
    """

    value = str(value or "").strip().lower()

    aliases = {
        "cache": "cached",
        "cached": "cached",
        "cache_status": "cached",
        "cache-status": "cached",
        "cache status": "cached",
        "cachestatus": "cached",

        "resolution": "resolution",
        "quality": "quality",
        "quality_score": "quality",
        "quality-score": "quality",
        "quality score": "quality",

        "seeders": "seeders",
        "seeds": "seeders",
        "seed": "seeders",

        "leechers": "leechers",
        "leeches": "leechers",
        "leech": "leechers",

        "size": "size",
        "size_bytes": "size",
        "size-bytes": "size",
    }

    return aliases.get(value, value)


def _normalize_criteria(sort_criteria) -> list[str]:
    if not sort_criteria:
        return [
            "cached",
            "resolution",
            "seeders",
            "quality",
        ]

    if isinstance(sort_criteria, str):
        sort_criteria = sort_criteria.split(",")

    normalized = []

    for criterion in sort_criteria:
        value = _normalize_criterion(criterion)

        if value and value not in normalized:
            normalized.append(value)

    return normalized or [
        "cached",
        "resolution",
        "seeders",
        "quality",
    ]


# ---------------------------------------------------------
# CACHE
# ---------------------------------------------------------

def _cache_rank(
    torrent: TorrentResult,
    cache_status_map: dict | None,
) -> int:
    """
    Higher is better.

        cached     = 2
        unknown    = 1
        uncached   = 0

    Handles CacheStatus enum values as well as strings.
    """

    if not cache_status_map:
        return 1

    info_hash = str(
        getattr(torrent, "info_hash", "") or ""
    ).lower()

    status = cache_status_map.get(info_hash)

    if status is None:
        original_hash = getattr(
            torrent,
            "info_hash",
            "",
        )
        status = cache_status_map.get(
            original_hash
        )

    if status is None:
        return 1

    # Enum values such as:
    #
    # CacheStatus.CACHED
    #
    # become:
    #
    # "CacheStatus.CACHED"
    #
    # while normal strings become:
    #
    # "cached"

    status_string = str(
        getattr(status, "value", status)
    ).strip().lower()

    if status_string in {
        "cached",
        "cache",
        "true",
        "available",
    }:
        return 2

    if status_string in {
        "not_cached",
        "not-cached",
        "not cached",
        "uncached",
        "false",
        "unavailable",
    }:
        return 0

    if (
        "not_cached" in status_string
        or "not-cached" in status_string
        or "not cached" in status_string
        or "uncached" in status_string
    ):
        return 0

    if "cached" in status_string:
        return 2

    return 1


# ---------------------------------------------------------
# RESOLUTION
# ---------------------------------------------------------

def _resolution_score(
    torrent: TorrentResult,
) -> int:

    quality = str(
        getattr(torrent, "quality", "") or ""
    ).lower()

    title = str(
        getattr(torrent, "title", "") or ""
    ).lower()

    value = f"{quality} {title}"

    if "2160p" in value or "4k" in value:
        return 2160

    if "1440p" in value:
        return 1440

    if "1080p" in value:
        return 1080

    if "720p" in value:
        return 720

    if "576p" in value:
        return 576

    if "480p" in value:
        return 480

    if "360p" in value:
        return 360

    if "240p" in value:
        return 240

    return 0


# ---------------------------------------------------------
# QUALITY
# ---------------------------------------------------------

def _quality_score(
    torrent: TorrentResult,
) -> int:

    quality = str(
        getattr(torrent, "quality", "") or ""
    ).lower()

    title = str(
        getattr(torrent, "title", "") or ""
    ).lower()

    value = f"{quality} {title}"

    scores = {
        "remux": 100,
        "bluray": 90,
        "blu-ray": 90,
        "web-dl": 80,
        "web dl": 80,
        "webrip": 70,
        "web rip": 70,
        "hdtv": 60,
        "dvdrip": 50,
        "brrip": 40,
        "hdrip": 30,
        "cam": 10,
        "ts": 5,
        "telesync": 5,
    }

    for key, score in scores.items():
        if key in value:
            return score

    return 0


# ---------------------------------------------------------
# SORT VALUE
# ---------------------------------------------------------

def _sort_value(
    torrent: TorrentResult,
    criterion: str,
    cache_status_map: dict | None,
):
    criterion = _normalize_criterion(
        criterion
    )

    if criterion == "cached":
        return _cache_rank(
            torrent,
            cache_status_map,
        )

    if criterion == "resolution":
        return _resolution_score(
            torrent
        )

    if criterion == "seeders":
        return (
            getattr(
                torrent,
                "seeders",
                0,
            )
            or 0
        )

    if criterion == "leechers":
        return (
            getattr(
                torrent,
                "leechers",
                0,
            )
            or 0
        )

    if criterion == "size":
        return (
            getattr(
                torrent,
                "size_bytes",
                0,
            )
            or 0
        )

    if criterion == "quality":
        return _quality_score(
            torrent
        )

    return 0


# ---------------------------------------------------------
# SORT
# ---------------------------------------------------------

def sort_torrents(
    torrents: List[TorrentResult],
    sort_criteria: List[str] | None = None,
    sort_order: str = "desc",
    allow_season_packs: bool = False,
    cache_status_map: dict | None = None,
) -> List[TorrentResult]:

    if not torrents:
        return []

    criteria = _normalize_criteria(
        sort_criteria
    )

    # -----------------------------------------------------
    # SEASON PACK FILTER
    # -----------------------------------------------------

    if not allow_season_packs:
        torrents = [
            torrent
            for torrent in torrents
            if not _is_season_pack(
                torrent.title
            )
        ]

    if not torrents:
        return []

    # -----------------------------------------------------
    # SORT
    # -----------------------------------------------------

    reverse = (
        str(sort_order or "desc")
        .strip()
        .lower()
        == "desc"
    )

    # Python tuple sorting gives us exactly what we want:
    #
    # ["cached", "resolution", "seeders"]
    #
    # becomes:
    #
    # (
    #     cache_rank,
    #     resolution,
    #     seeders,
    # )
    #
    # Therefore cache is ONLY the primary criterion if
    # the user actually put it first.
    #
    # If the user instead chooses:
    #
    # ["resolution", "cached", "seeders"]
    #
    # resolution becomes primary and cache becomes a
    # tiebreaker.
    #
    # This is the important difference from the old sorter.

    def sort_key(torrent):
        return tuple(
            _sort_value(
                torrent,
                criterion,
                cache_status_map,
            )
            for criterion in criteria
        )

    sorted_results = sorted(
        torrents,
        key=sort_key,
        reverse=reverse,
    )

    # -----------------------------------------------------
    # DEBUG
    # -----------------------------------------------------

    print(
        "SORT CRITERIA:",
        criteria,
        "| ORDER:",
        "DESC" if reverse else "ASC",
        flush=True,
    )

    for index, torrent in enumerate(
        sorted_results[:20],
        start=1,
    ):
        values = tuple(
            _sort_value(
                torrent,
                criterion,
                cache_status_map,
            )
            for criterion in criteria
        )

        print(
            f"SORT #{index:02d}: "
            f"{values} | "
            f"cached={_cache_rank(torrent, cache_status_map)} | "
            f"resolution={_resolution_score(torrent)} | "
            f"seeders={getattr(torrent, 'seeders', 0) or 0} | "
            f"quality={_quality_score(torrent)} | "
            f"title={torrent.title}",
            flush=True,
        )

    return sorted_results


# ---------------------------------------------------------
# SEASON PACK DETECTION
# ---------------------------------------------------------

def _is_season_pack(
    title: str,
) -> bool:

    title = str(
        title or ""
    ).lower()

    season_pack_patterns = [
        "season 1",
        "season 2",
        "season 3",
        "season 4",
        "season 5",
        "season 6",
        "season 7",
        "season 8",
        "season 9",
        "season 10",
        "season 11",
        "season 12",
        "season 13",
        "season 14",
        "season 15",
        "season 16",
        "season 17",
        "season 18",
        "season 19",
        "season 20",
        "complete season",
        "complete series",
        "complete collection",
        "series complete",
    ]

    return any(
        pattern in title
        for pattern in season_pack_patterns
    )
