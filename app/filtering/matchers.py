import re


LANGUAGE_PATTERNS = {

    "spanish": [
        r"\bespañol\b",
        r"\besp\b",
        r"\bspanish\b",
        r"\bspa\b",
    ],

    "french": [
        r"\bfrench\b",
        r"\bfrançais\b",
        r"\bfra\b",
    ],

    "german": [
        r"\bgerman\b",
        r"\bdeutsch\b",
        r"\bger\b",
    ],

    "italian": [
        r"\bitalian\b",
        r"\bitaliano\b",
        r"\bita\b",
    ],

    "portuguese": [
        r"\bportuguese\b",
        r"\bportuguês\b",
        r"\bpor\b",
    ],

    "japanese": [
        r"\bjapanese\b",
        r"\bjpn\b",
        r"\b日本語\b",
    ],

    "korean": [
        r"\bkorean\b",
        r"\bkor\b",
        r"\b한국어\b",
    ],

    "chinese": [
        r"\bchinese\b",
        r"\bzh\b",
        r"\b中文\b",
    ],
}


FOREIGN_LANGUAGE_PATTERNS = []

for patterns in LANGUAGE_PATTERNS.values():
    FOREIGN_LANGUAGE_PATTERNS.extend(patterns)



CODEC_PATTERNS = {

    "hevc": [
        r"\bx265\b",
        r"\bhevc\b",
    ],

    "h264": [
        r"\bx264\b",
        r"\bh264\b",
    ],

    "av1": [
        r"\bav1\b",
    ],

    "remux": [
        r"\bremux\b",
    ],

    "dv": [
        r"\bdv\b",
        r"dolby vision",
    ],
}



def _match_patterns(title_lower, patterns):

    for pat in patterns:

        if re.search(
            pat,
            title_lower
        ):
            return True

    return False



def matches_language(
    title: str,
    allowed: list[str],
) -> bool:

    """
    Language filtering.

    English is assumed unless a foreign language
    is explicitly detected.
    """

    if not allowed:
        return True


    title_lower = title.lower()


    # English is default
    if "english" in [
        x.lower()
        for x in allowed
    ]:

        for pattern in FOREIGN_LANGUAGE_PATTERNS:

            if re.search(
                pattern,
                title_lower
            ):
                return False

        return True



    # Other languages require explicit match

    for lang in allowed:

        patterns = LANGUAGE_PATTERNS.get(
            lang.lower()
        )

        if patterns and _match_patterns(
            title_lower,
            patterns
        ):
            return True


    return False



def matches_codec(
    title: str,
    allowed: list[str],
) -> bool:

    if not allowed:
        return True


    title_lower = title.lower()


    for codec in allowed:

        patterns = CODEC_PATTERNS.get(
            codec.lower()
        )


        if patterns and _match_patterns(
            title_lower,
            patterns
        ):
            return True


    return False