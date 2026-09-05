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

    "arabic": [
        r"\barabic\b",
        r"\bar\b",
    ],

    "bulgarian": [
        r"\bbulgarian\b",
        r"\bbul\b",
    ],

    "bengali": [
        r"\bbengali\b",
        r"\bben\b",
    ],

    "czech": [
        r"\bczech\b",
        r"\bcze\b",
    ],

    "danish": [
        r"\bdanish\b",
        r"\bdan\b",
    ],

    "greek": [
        r"\bgreek\b",
        r"\bel\b",
    ],

    "english": [
        r"\benglish\b",
        r"\beng\b",
    ],

    "estonian": [
        r"\bestonian\b",
        r"\best\b",
    ],

    "persian": [
        r"\bpersian\b",
        r"\bfarsi\b",
    ],

    "finnish": [
        r"\bfinnish\b",
        r"\bfin\b",
    ],

    "gujarati": [
        r"\bgujarati\b",
        r"\bguj\b",
    ],

    "hebrew": [
        r"\bhebrew\b",
        r"\bheb\b",
    ],

    "hindi": [
        r"\bhindi\b",
        r"\bhin\b",
    ],

    "croatian": [
        r"\bcroatian\b",
        r"\bcro\b",
    ],

    "hungarian": [
        r"\bhungarian\b",
        r"\bhun\b",
    ],

    "indonesian": [
        r"\bindonesian\b",
        r"\bind\b",
    ],

    "kannada": [
        r"\bkannada\b",
        r"\bkan\b",
    ],

    "latino": [
        r"\blatino\b",
        r"\blat\b",
    ],

    "lithuanian": [
        r"\blithuanian\b",
        r"\blit\b",
    ],

    "latvian": [
        r"\blatvian\b",
        r"\blav\b",
    ],

    "malayalam": [
        r"\bmalayalam\b",
        r"\bmal\b",
    ],

    "marathi": [
        r"\bmarathi\b",
        r"\bmar\b",
    ],

    "dutch": [
        r"\bdutch\b",
        r"\bnld\b",
    ],

    "norwegian": [
        r"\bnorwegian\b",
        r"\bnor\b",
    ],

    "punjabi": [
        r"\bpunjabi\b",
        r"\bpan\b",
    ],

    "polish": [
        r"\bpolish\b",
        r"\bpol\b",
    ],

    "romanian": [
        r"\bromanian\b",
        r"\brom\b",
    ],

    "russian": [
        r"\brussian\b",
        r"\brus\b",
    ],

    "slovak": [
        r"\bslovak\b",
        r"\bslk\b",
    ],

    "slovenian": [
        r"\bslovenian\b",
        r"\bslv\b",
    ],

    "serbian": [
        r"\bserbian\b",
        r"\bsrp\b",
    ],

    "swedish": [
        r"\bswedish\b",
        r"\bswe\b",
    ],

    "tamil": [
        r"\btamil\b",
        r"\btam\b",
    ],

    "telugu": [
        r"\btelugu\b",
        r"\btel\b",
    ],

    "thai": [
        r"\bthai\b",
        r"\btha\b",
    ],

    "turkish": [
        r"\bturkish\b",
        r"\btur\b",
    ],

    "ukrainian": [
        r"\bukrainian\b",
        r"\bukr\b",
    ],

    "vietnamese": [
        r"\bvietnamese\b",
        r"\bvie\b",
    ],

    "multi": [
        r"\bmulti\b",
        r"\bdual\b",
        r"\bdual audio\b",
    ],
}


FOREIGN_LANGUAGE_PATTERNS = []

for lang, patterns in LANGUAGE_PATTERNS.items():
    if lang != "multi":  # Exclude multi from foreign language patterns
        FOREIGN_LANGUAGE_PATTERNS.extend(patterns)



CODEC_PATTERNS = {

    "hevc": [
        r"\bx265\b",
        r"\bh[. ]?265\b",
        r"\bhevc\b",
    ],

    "h264": [
        r"\bx264\b",
        r"\bh[. ]?264\b",
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


def matches_required_languages(
    title: str,
    required: list[str],
) -> bool:
    """
    Check if title contains at least one of the required languages.
    If no required languages specified, returns True (no restriction).
    """
    if not required:
        return True

    title_lower = title.lower()

    for lang in required:
        patterns = LANGUAGE_PATTERNS.get(lang.lower())
        if patterns and _match_patterns(title_lower, patterns):
            return True

    return False


def matches_excluded_languages(
    title: str,
    excluded: list[str],
) -> bool:
    """
    Check if title contains any of the excluded languages.
    Returns False if any excluded language is found.
    If no excluded languages specified, returns True (no restriction).
    """
    if not excluded:
        return True

    title_lower = title.lower()

    for lang in excluded:
        patterns = LANGUAGE_PATTERNS.get(lang.lower())
        if patterns and _match_patterns(title_lower, patterns):
            return False  # Found an excluded language

    return True  # No excluded languages found



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