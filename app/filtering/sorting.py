import re
from typing import List, Optional, TYPE_CHECKING
from app.models import TorrentResult

if TYPE_CHECKING:
    from app.models import CacheStatus


def quality_score(title: str) -> int:

    t = title.lower()

    score = 0

    # Resolution priority
    if re.search(r"\b(2160p|4k|uhd)\b", t):
        score += 5000

    elif re.search(r"\b1440p\b", t):
        score += 4000

    elif re.search(r"\b1080p\b", t):
        score += 3000

    elif re.search(r"\b720p\b", t):
        score += 2000

    elif re.search(r"\b(576p|480p|360p)\b", t):
        score += 1000


    # Quality bonuses
    if "remux" in t:
        score += 500

    if "dolby vision" in t or re.search(r"\bdv\b", t):
        score += 400

    if "hdr" in t:
        score += 200

    if "atmos" in t:
        score += 100

    if "hevc" in t or "x265" in t:
        score += 100


    return score


def detect_resolution(title: str) -> str:
    """Detect resolution from title and return a sortable value."""
    t = title.lower()
    
    if re.search(r"\b(2160p|4k|uhd)\b", t):
        return "2160p"
    elif re.search(r"\b1440p\b", t):
        return "1440p"
    elif re.search(r"\b1080p\b", t):
        return "1080p"
    elif re.search(r"\b720p\b", t):
        return "720p"
    elif re.search(r"\b576p\b", t):
        return "576p"
    elif re.search(r"\b480p\b", t):
        return "480p"
    elif re.search(r"\b360p\b", t):
        return "360p"
    elif re.search(r"\b240p\b", t):
        return "240p"
    return "unknown"


def is_season_pack(title: str) -> bool:
    """Detect if torrent is a season pack."""
    t = title.lower()
    return bool(re.search(r"\b(season\s*\d+|complete\s*season|s\d{1,2}\.complete|full\s*season)\b", t))


def sort_torrents(
    torrents: List[TorrentResult],
    sort_criteria: List[str] = None,
    sort_order: str = "desc",
    allow_season_packs: bool = False,
    cache_status_map: Optional[dict] = None
) -> List[TorrentResult]:
    """
    Sort torrents based on user preferences with multi-level sorting.
    
    Uses Comet's two-pass approach for cache prioritization:
    - If "cached" is in criteria and sort_order is "desc", cached torrents are selected first
    - Then uncached torrents are selected in the remaining order
    - This ensures cached streams always appear at the top
    
    Args:
        torrents: List of torrents to sort
        sort_criteria: List of sort fields in priority order (e.g., ["seeders", "resolution", "quality"])
        sort_order: Sort order (asc, desc) - applies to all criteria
        allow_season_packs: Whether to allow season packs
        cache_status_map: Dictionary of info_hash -> CacheStatus (optional)
    """
    if sort_criteria is None:
        sort_criteria = ["seeders", "resolution", "quality"]
    
    # Filter season packs if not allowed
    if not allow_season_packs:
        torrents = [t for t in torrents if not is_season_pack(t.title)]
    
    # Check if we should prioritize cached streams (Comet's approach)
    prioritize_cached = (
        "cached" in sort_criteria 
        and sort_order == "desc" 
        and cache_status_map
    )

    if prioritize_cached:
        # Two-pass selection: cached first, then uncached
        cached_torrents = []
        uncached_torrents = []
        
        for torrent in torrents:
            cache_status = cache_status_map.get(torrent.info_hash)
            if not cache_status:
                cache_status = cache_status_map.get(torrent.info_hash.lower())
            
            # Check if cached
            cache_str = str(cache_status).lower() if cache_status else ""
            is_cached = "cached" in cache_str
            
            if is_cached:
                cached_torrents.append(torrent)
            else:
                uncached_torrents.append(torrent)
        
        # Sort each group by remaining criteria (excluding "cached")
        remaining_criteria = [c for c in sort_criteria if c != "cached"]
        if remaining_criteria:
            cached_torrents = _sort_by_criteria(cached_torrents, remaining_criteria, sort_order)
            uncached_torrents = _sort_by_criteria(uncached_torrents, remaining_criteria, sort_order)
        
        # Combine: cached first, then uncached
        print(f"Sorted: {len(cached_torrents)} cached + {len(uncached_torrents)} uncached", flush=True)
        return cached_torrents + uncached_torrents
    else:
        # Normal sorting with all criteria
        return _sort_by_criteria(torrents, sort_criteria, sort_order)


def _sort_by_criteria(
    torrents: List[TorrentResult],
    sort_criteria: List[str],
    sort_order: str
) -> List[TorrentResult]:
    """Helper function to sort torrents by criteria (excluding cache status)."""
    # Define get value function for each criterion
    def get_sort_value(torrent: TorrentResult, criterion: str):
        title = torrent.title.lower()
        
        if criterion == "seeders":
            return torrent.seeders or 0
            
        elif criterion == "size":
            return torrent.size_bytes or 0
            
        elif criterion == "resolution":
            resolution_order = {
                "2160p": 5, "4k": 5, "uhd": 5,
                "1440p": 4,
                "1080p": 3,
                "720p": 2,
                "576p": 1.5,
                "480p": 1,
                "360p": 0.5,
                "240p": 0.25,
                "unknown": 0
            }
            return resolution_order.get(detect_resolution(title), 0)
            
        elif criterion == "quality":
            return quality_score(title)
            
        else:
            return quality_score(title)
    
    reverse = sort_order == "desc"
    
    sorted_torrents = sorted(
        torrents,
        key=lambda t: tuple(get_sort_value(t, criterion) for criterion in sort_criteria),
        reverse=reverse
    )
    
    return sorted_torrents
