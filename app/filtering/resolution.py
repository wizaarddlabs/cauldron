import re


RESOLUTION_PATTERNS = {
    "2160p": [
        r"\b2160p\b",
        r"\b4k\b",
        r"\buhd\b",
    ],

    "1080p": [
        r"\b1080p\b",
        r"\bfullhd\b",
    ],

    "720p": [
        r"\b720p\b",
    ],
}


def matches_resolution(
    title: str,
    allowed: list[str],
) -> bool:
    """
    Returns True if torrent title matches
    one of the allowed resolutions.
    """

    if not allowed:
        return True


    title_lower = title.lower()


    for resolution in allowed:

        patterns = RESOLUTION_PATTERNS.get(
            resolution
        )

        if not patterns:
            continue


        for pattern in patterns:

            if re.search(
                pattern,
                title_lower
            ):
                return True


    return False


def detect_resolution(title: str) -> str | None:
    """
    Detects and returns the resolution string (e.g. "2160p") found
    in `title`, or `None` if none matched.
    """

    title_lower = title.lower()

    for resolution, patterns in RESOLUTION_PATTERNS.items():

        for pattern in patterns:

            if re.search(pattern, title_lower):
                return resolution

    return None