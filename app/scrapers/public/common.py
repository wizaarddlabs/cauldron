"""Helpers shared by the public torrent scrapers."""

import re

# Quality extraction patterns

_QUALITY_PATTERN = re.compile(
    r"\b(2160p|4K|1080p|720p|480p|CAM|HDCAM|TS|WEBRip|BluRay|DVDRip)\b",
    re.IGNORECASE,
)

# Size parsing patterns

_SIZE_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(GB|MB|KB|TB)",
    re.IGNORECASE,
)


def extract_quality(
    title: str,
) -> str | None:
    """Extract quality from torrent title."""

    if not title:
        return None

    match = _QUALITY_PATTERN.search(title)

    if match:
        return match.group(1).upper()

    return None


def parse_size(
    size_str: str,
) -> int | None:
    """Convert a human-readable torrent size to bytes."""

    if not size_str:
        return None

    match = _SIZE_PATTERN.search(
        str(size_str)
    )

    if not match:
        return None

    try:
        value = float(match.group(1))
        unit = match.group(2).upper()

        multipliers = {
            "KB": 1024,
            "MB": 1024 ** 2,
            "GB": 1024 ** 3,
            "TB": 1024 ** 4,
        }

        return int(
            value * multipliers[unit]
        )

    except (
        ValueError,
        TypeError,
        KeyError,
    ):
        return None
