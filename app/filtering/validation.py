"""Torrent validation utilities."""

import re
from typing import Optional


def validate_torrent_title(
    torrent_title: str,
    expected_title: str,
    expected_year: int | None,
    media_type: str,
    aka_titles: Optional[list[str]] = None,
    similarity_threshold: int = 75,
) -> tuple[bool, str]:
    """Return whether a torrent title plausibly belongs to the requested item."""
    def normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    normalized_torrent = normalize(torrent_title)
    candidate_titles = [expected_title, *(aka_titles or [])]
    normalized_candidates = [normalize(candidate) for candidate in candidate_titles if candidate]

    # Require the complete title in word order. Token-set matching alone turns
    # "Breaking Bad" into a false positive for "The Bad Guys Breaking In".
    matches = [candidate for candidate in normalized_candidates if candidate in normalized_torrent]
    if not matches:
        return False, "Requested title is not present in the torrent name"

    from rapidfuzz import fuzz
    similarity = max(fuzz.token_set_ratio(normalized_torrent, candidate) for candidate in matches)
    if similarity < similarity_threshold:
        return False, f"Low title similarity ({similarity:.0f}%)"

    years = {int(value) for value in re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", torrent_title)}
    if media_type == "movie" and expected_year and years and expected_year not in years:
        return False, f"Year mismatch (torrent: {sorted(years)}, expected: {expected_year})"

    if media_type == "movie" and is_tv_show_pattern(torrent_title):
        return False, "Movie has a TV episode or season pattern"

    return True, f"Valid ({similarity:.0f}% title similarity)"


def is_tv_show_pattern(title: str) -> bool:
    """Check if title contains TV show patterns."""
    tv_patterns = [
        r"\.S\d{2}E\d{2}\.",
        r"\.S\d+E\d+\.",
        r"\s+\d+x\d+\s",
        r"\.season\s+",
        r"\.episode\s+",
    ]
    return any(re.search(pattern, title, re.IGNORECASE) for pattern in tv_patterns)
