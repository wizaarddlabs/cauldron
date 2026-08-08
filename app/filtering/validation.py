"""Torrent title validation utilities."""

import re
from typing import Optional

from rapidfuzz import fuzz


def normalize(value: str) -> str:
    """
    Normalize a title for reliable comparison.

    Converts punctuation/separators to spaces and collapses
    repeated whitespace.
    """
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def title_tokens(value: str) -> list[str]:
    """Return normalized title tokens."""
    return normalize(value).split()


def contains_title(
    torrent_title: str,
    candidate_title: str,
) -> bool:
    """
    Require the complete normalized title to appear in the torrent name.

    This deliberately avoids token-set-only matching because that can
    produce false positives such as:
        "The Bad Guys Breaking In"
    matching:
        "Breaking Bad"
    """
    torrent = normalize(torrent_title)
    candidate = normalize(candidate_title)

    if not candidate:
        return False

    return candidate in torrent


def is_tv_show_pattern(title: str) -> bool:
    """Return True when a title clearly looks like a TV release."""
    tv_patterns = [
        # S01E02 / S1E2 / S01E002
        r"\bs\d{1,2}e\d{1,3}\b",

        # 1x02 / 01x02
        r"\b\d{1,2}x\d{1,3}\b",

        # Season 1 / Season 01
        r"\bseason[\s._-]*\d{1,2}\b",

        # Episode 1 / Episode 01
        r"\bepisode[\s._-]*\d{1,3}\b",

        # Common scene/release naming forms
        r"\bep[\s._-]*\d{1,3}\b",

        # Complete season releases
        r"\bcomplete[\s._-]*season\b",
        r"\bfull[\s._-]*season\b",
        r"\bseason[\s._-]*\d{1,2}[\s._-]*(complete|full)\b",
    ]

    return any(
        re.search(pattern, title, re.IGNORECASE)
        for pattern in tv_patterns
    )


def is_episode_pattern(
    title: str,
    season: str,
    episode: str,
) -> bool:
    """
    Check whether a torrent explicitly contains the requested episode.
    """
    try:
        s = int(season)
        e = int(episode)
    except (TypeError, ValueError):
        return False

    patterns = [
        rf"\bs{s:02d}e{e:02d}\b",
        rf"\bs{s}e{e}\b",
        rf"\b{s:02d}x{e:02d}\b",
        rf"\b{s}x{e}\b",
    ]

    normalized = title.lower()

    return any(
        re.search(pattern, normalized, re.IGNORECASE)
        for pattern in patterns
    )


def validate_torrent_title(
    torrent_title: str,
    expected_title: str,
    expected_year: int | None,
    media_type: str,
    aka_titles: Optional[list[str]] = None,
    similarity_threshold: int = 75,
) -> tuple[bool, str]:
    """
    Return whether a torrent title plausibly belongs to the requested item.

    Validation is intentionally conservative. A torrent should be rejected
    rather than allowed through when the title is ambiguous.
    """

    candidate_titles = [
        expected_title,
        *(aka_titles or []),
    ]

    # Remove duplicates after normalization.
    normalized_candidates: list[str] = []
    seen: set[str] = set()

    for candidate in candidate_titles:
        if not isinstance(candidate, str) or not candidate.strip():
            continue

        normalized = normalize(candidate)

        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_candidates.append(normalized)

    if not normalized_candidates:
        return False, "No valid requested title"

    normalized_torrent = normalize(torrent_title)

    # ---------------------------------------------------------
    # TITLE MATCH
    # ---------------------------------------------------------

    matched_candidates = [
        candidate
        for candidate in normalized_candidates
        if candidate in normalized_torrent
    ]

    if not matched_candidates:
        return False, "Requested title is not present in torrent name"

    # Use the strongest matching title.
    similarity = max(
        fuzz.token_set_ratio(normalized_torrent, candidate)
        for candidate in matched_candidates
    )

    if similarity < similarity_threshold:
        return False, f"Low title similarity ({similarity:.0f}%)"

    # ---------------------------------------------------------
    # MOVIE VALIDATION
    # ---------------------------------------------------------

    if media_type == "movie":

        # Reject obvious TV releases.
        if is_tv_show_pattern(torrent_title):
            return False, "Movie has a TV episode or season pattern"

        # If the torrent explicitly contains a year, it must be the
        # requested movie year.
        years = {
            int(value)
            for value in re.findall(
                r"(?<!\d)(?:19|20)\d{2}(?!\d)",
                torrent_title,
            )
        }

        if (
            expected_year
            and years
            and expected_year not in years
        ):
            return (
                False,
                f"Year mismatch "
                f"(torrent: {sorted(years)}, expected: {expected_year})",
            )

    # ---------------------------------------------------------
    # SERIES VALIDATION
    # ---------------------------------------------------------

    if media_type == "series":

        # A series torrent is allowed to be:
        #
        #   Show.Name.S01E02
        #   Show.Name.S01E01-E05
        #   Show.Name.S01
        #   Show.Name.Season.1
        #
        # Episode-specific filtering is performed separately by
        # stremio.py, so don't reject season packs here.
        pass

    return True, f"Valid ({similarity:.0f}% title similarity)"