"""
Cauldron torrent sorting.

Supports multi-level sorting and explicit cache prioritization.

When "cached" is included as a sorting criterion with descending order,
cached torrents are placed before uncached torrents. The remaining criteria
are then applied independently within each group.
"""

from typing import List

from app.models import TorrentResult


def _sort_by_criteria(
    torrents: List[TorrentResult],
    sort_criteria: List[str],
    sort_order: str,
) -> List[TorrentResult]:

    def resolution_score(title: str) -> int:
        title = title.lower()

        if "2160p" in title or "4k" in title:
            return 2160

        if "1440p" in title:
            return 1440

        if "1080p" in title:
            return 1080

        if "720p" in title:
            return 720

        if "576p" in title:
            return 576

        if "480p" in title:
            return 480

        return 0

    def quality_score(title: str) -> int:
        title = title.lower()

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
            if key in title:
                return score

        return 0

    def get_sort_value(
        torrent: TorrentResult,
        criterion: str,
    ):
        title = torrent.title.lower()

        if criterion == "seeders":
            return getattr(torrent, "seeders", 0) or 0

        if criterion == "leechers":
            return getattr(torrent, "leechers", 0) or 0

        if criterion == "size":
            return getattr(torrent, "size_bytes", 0) or 0

        if criterion == "resolution":
            return resolution_score(title)

        if criterion == "quality":
            return quality_score(title)

        return 0

    reverse = sort_order == "desc"

    return sorted(
        torrents,
        key=lambda torrent: tuple(
            get_sort_value(torrent, criterion)
            for criterion in sort_criteria
        ),
        reverse=reverse,
    )


def sort_torrents(
    torrents: List[TorrentResult],
    sort_criteria: List[str] | None = None,
    sort_order: str = "desc",
    allow_season_packs: bool = False,
    cache_status_map: dict | None = None,
) -> List[TorrentResult]:

    if not torrents:
        return []

    sort_criteria = sort_criteria or [
        "cached",
        "seeders",
        "resolution",
        "quality",
    ]

    # Remove season packs unless explicitly enabled.
    if not allow_season_packs:
        torrents = [
            torrent
            for torrent in torrents
            if not _is_season_pack(torrent.title)
        ]

    # ---------------------------------------------------------
    # CACHE PRIORITIZATION
    # ---------------------------------------------------------

    prioritize_cached = (
        "cached" in sort_criteria
        and sort_order == "desc"
        and cache_status_map
    )

    if prioritize_cached:
        cached_torrents = []
        uncached_torrents = []
        unknown_torrents = []

        for torrent in torrents:
            info_hash = str(
                getattr(torrent, "info_hash", "")
            ).lower()

            status = cache_status_map.get(info_hash)

            if status is None:
                # Try original casing as a fallback.
                status = cache_status_map.get(
                    getattr(torrent, "info_hash", "")
                )

            status_string = (
                str(status).lower()
                if status is not None
                else ""
            )

            if (
                status_string.endswith("cached")
                or status_string == "cached"
                or (
                    "cached" in status_string
                    and "not" not in status_string
                )
            ):
                cached_torrents.append(torrent)

            elif (
                "not_cached" in status_string
                or "not cached" in status_string
                or "uncached" in status_string
            ):
                uncached_torrents.append(torrent)

            else:
                unknown_torrents.append(torrent)

        # Cache is a grouping criterion, not a second copy of sorting.
        remaining_criteria = [
            criterion
            for criterion in sort_criteria
            if criterion != "cached"
        ]

        if remaining_criteria:
            cached_torrents = _sort_by_criteria(
                cached_torrents,
                remaining_criteria,
                sort_order,
            )

            uncached_torrents = _sort_by_criteria(
                uncached_torrents,
                remaining_criteria,
                sort_order,
            )

            unknown_torrents = _sort_by_criteria(
                unknown_torrents,
                remaining_criteria,
                sort_order,
            )

        print(
            "Sorted cache groups: "
            f"{len(cached_torrents)} cached + "
            f"{len(uncached_torrents)} uncached + "
            f"{len(unknown_torrents)} unknown",
            flush=True,
        )

        return (
            cached_torrents
            + uncached_torrents
            + unknown_torrents
        )

    # ---------------------------------------------------------
    # NORMAL SORTING
    # ---------------------------------------------------------

    normal_criteria = [
        criterion
        for criterion in sort_criteria
        if criterion != "cached"
    ]

    if not normal_criteria:
        normal_criteria = [
            "seeders",
            "resolution",
            "quality",
        ]

    return _sort_by_criteria(
        torrents,
        normal_criteria,
        sort_order,
    )


def _is_season_pack(title: str) -> bool:
    title = title.lower()

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