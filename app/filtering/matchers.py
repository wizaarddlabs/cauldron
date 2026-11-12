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

    "dubbed": [
        r"\bdubbed\b",
        r"\bdub\b",
        r"\bdubs\b",
        r"\bdoblad[oa]\b",
        r"\bdoblaje\b",
        r"\bdublad[oa]\b",
        r"\bdublagem\b",
    ],

    "multi": [
        r"\bmulti\b",
        r"\bdual\b",
        r"\bdual audio\b",
    ],
}


# Not languages in themselves: a release can be multi-audio or dubbed into
# any language.
NON_LANGUAGE_TAGS = {"multi", "dubbed"}

# Pseudo-language for releases that carry no language tag at all.
UNKNOWN_LANGUAGE = "unknown"

FOREIGN_LANGUAGE_PATTERNS = []

for lang, patterns in LANGUAGE_PATTERNS.items():
    if lang not in NON_LANGUAGE_TAGS and lang != "english":
        FOREIGN_LANGUAGE_PATTERNS.extend(patterns)


# ---------------------------------------------------------
# LANGUAGE TAG DETECTION
# ---------------------------------------------------------
#
# Language codes are short ("el", "por", "pan", "ben", "lat") and collide
# with ordinary title words: "El Camino" is not Greek and "Peter Pan" is not
# Punjabi. A word only counts as a language tag when it is where release
# names put tags:
#
#   * after the first year / resolution / episode / source marker
#       Movie.2024.SPA.LAT.1080p     Show S01E02 [ITA]
#   * inside brackets or parentheses          Pelicula [Latino] 1080p
#   * written in capitals (unless the whole title is in capitals)
#       Movie ITA 1080p
#   * next to another language code            Movie.Ita.Eng.1080p

_TAG_BOUNDARY = re.compile(
    r"\b(?:19\d{2}|20\d{2}|\d{3,4}p|4k|uhd|s\d{1,2}(?:e\d{1,3})?|"
    r"\d{1,2}x\d{2}|season|temporada|complete|web(?:-?dl|rip)?|bluray|blu-ray|"
    r"bdrip|brrip|hdtv|hdrip|dvdrip|remux)\b",
    re.IGNORECASE,
)

_BRACKETED = re.compile(r"[\[(]([^\])]*)[\])]")

_WORD = re.compile(r"[^\W_]+")

# Every plain word that appears in a language pattern, e.g. "spa", "latino".
_LANGUAGE_WORDS = {
    word
    for patterns in LANGUAGE_PATTERNS.values()
    for pattern in patterns
    for word in [pattern.replace("\\b", "")]
    if _WORD.fullmatch(word)
}


def language_tag_text(title: str) -> str:
    """
    The parts of a release name that may carry language tags, lowercased.
    """

    if not title:
        return ""

    marker = _TAG_BOUNDARY.search(title)
    head = title[: marker.start()] if marker else title
    tail = title[marker.start():] if marker else ""

    # Without any marker we can't tell title words from tags; fall back to
    # the strict per-word rules below for the whole name.
    parts = [tail] + _BRACKETED.findall(head)

    head_words = _WORD.findall(_BRACKETED.sub(" ", head))
    letters = [c for c in head if c.isalpha()]
    head_all_caps = bool(letters) and all(c.isupper() for c in letters)

    for index, word in enumerate(head_words):
        lower = word.lower()

        if lower not in _LANGUAGE_WORDS:
            continue

        neighbours = {
            head_words[i].lower()
            for i in (index - 1, index + 1)
            if 0 <= i < len(head_words)
        }

        if (
            (len(word) >= 2 and word.isupper() and not head_all_caps)
            or neighbours & _LANGUAGE_WORDS
        ):
            parts.append(word)

    return " ".join(parts).lower()


def detect_languages(title: str) -> set[str]:
    """Language keys (and "multi" / "dubbed") tagged on a release name."""

    text = language_tag_text(title)

    return {
        lang
        for lang, patterns in LANGUAGE_PATTERNS.items()
        if _match_patterns(text, patterns)
    }


def _has_no_language_tag(detected: set[str]) -> bool:
    return not (detected - {"dubbed"})


def _matches_any(detected: set[str], languages: list[str]) -> bool:
    wanted = {lang.lower() for lang in languages}

    return bool(detected & wanted) or (
        UNKNOWN_LANGUAGE in wanted and _has_no_language_tag(detected)
    )



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

    return any(re.search(pat, title_lower) for pat in patterns)



def matches_language(
    title: str,
    allowed: list[str],
) -> bool:
    """
    Language filtering.

    English is assumed unless a foreign language is explicitly tagged.
    """

    if not allowed:
        return True

    detected = detect_languages(title)

    if "english" in [x.lower() for x in allowed]:
        return not (detected - NON_LANGUAGE_TAGS - {"english"})

    # Other languages require an explicit tag.
    return _matches_any(detected, allowed)


def matches_required_languages(
    title: str,
    required: list[str],
) -> bool:
    """
    True if the release is tagged with at least one required language.
    "unknown" matches releases without any language tag (often English).
    No required languages means no restriction.
    """

    if not required:
        return True

    return _matches_any(detect_languages(title), required)


def matches_excluded_languages(
    title: str,
    excluded: list[str],
) -> bool:
    """
    False if the release is tagged with any excluded language.
    "unknown" excludes releases without any language tag.
    No excluded languages means no restriction.
    """

    if not excluded:
        return True

    return not _matches_any(detect_languages(title), excluded)


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
