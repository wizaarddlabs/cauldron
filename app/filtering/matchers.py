import re

LANGUAGE_PATTERNS = {
    "english": [r"\benglish\b", r"\beng\b", r"\ben\b"],
    "spanish": [r"\bespañol\b", r"\besp\b", r"\bes\b", r"\bspanish\b"],
    "french": [r"\bfrench\b", r"\bfr\b", r"\bfrançais\b"],
    "german": [r"\bgerman\b", r"\bde\b", r"\bdeutsch\b"],
    "italian": [r"\bitalian\b", r"\bit\b", r"\bitaliano\b"],
    "portuguese": [r"\bportuguese\b", r"\bpt\b", r"\bportuguês\b"],
    "japanese": [r"\bjapanese\b", r"\bja\b", r"\bjpn\b", r"\b日本語\b"],
    "korean": [r"\bkorean\b", r"\bko\b", r"\bkr\b", r"\b한국어\b"],
    "chinese": [r"\bchinese\b", r"\bzh\b", r"\b中\b", r"\b中文\b"],
}

CODEC_PATTERNS = {
    "hevc": [r"\b(x265|hevc)\b"],
    "h264": [r"\b(x264|h264)\b"],
    "av1": [r"\b(av1)\b"],
    "remux": [r"\b(remux)\b"],
    "dv": [r"\b(dv|dolby vision)\b"],
}


def _match_patterns(title_lower: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if re.search(pat, title_lower):
            return True
    return False


def matches_language(title: str, allowed: list[str]) -> bool:
    """Return True if title matches any of the allowed languages.

    `allowed` contains language keys like 'english', 'spanish', or raw
    tokens which will be treated case-insensitively.
    """
    if not allowed:
        return True

    title_lower = title.lower()

    for lang in allowed:
        lang_key = lang.lower()
        patterns = LANGUAGE_PATTERNS.get(lang_key)
        if patterns:
            if _match_patterns(title_lower, patterns):
                return True
        else:
            # Fallback: simple substring match
            if lang_key in title_lower:
                return True

    return False


def matches_codec(title: str, allowed: list[str]) -> bool:
    """Return True if title matches any of the allowed codec keywords."""
    if not allowed:
        return True

    title_lower = title.lower()

    for codec in allowed:
        codec_key = codec.lower()
        patterns = CODEC_PATTERNS.get(codec_key)
        if patterns:
            if _match_patterns(title_lower, patterns):
                return True
        else:
            if codec_key in title_lower:
                return True

    return False
