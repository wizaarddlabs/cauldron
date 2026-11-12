"""
Decide whether a scraped torrent title actually belongs to the requested
movie or episode (title tokens, year, aliases, SxxEyy / season packs).
"""

import logging
import re
import unicodedata

from app.filtering.matchers import NON_LANGUAGE_TAGS, detect_languages
from app.models import TorrentResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# TITLE NORMALIZATION
# ---------------------------------------------------------


def _normalize_title(value: str | None) -> str:
    """
    Normalize a release/title for comparison.

    Examples:
        "Cars: The Movie" -> "cars: the movie"
        "Cars.2006.1080p" -> "cars 2006 1080p"
        "The.Cars.That.Drove.Us" -> "the cars that drove us"
    """

    if not value:
        return ""

    # Fold accents so "Amélie" / "Pokémon" match "Amelie" / "Pokemon".
    value = "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )

    value = value.lower()

    # Replace common release separators with spaces.
    value = re.sub(r"[._\-]+", " ", value)

    # Remove brackets/parentheses but preserve contents.
    value = re.sub(r"[\[\](){}]", " ", value)

    # Normalize ampersands so:
    #   "Minions & Monsters"
    #   "Minions and Monsters"
    # are treated as the same title.
    value = value.replace("&", " and ")

    # Normalize apostrophes.
    value = value.replace("'", "").replace("\u2019", "")

    # Collapse whitespace.
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def _title_tokens(value: str | None) -> list[str]:
    normalized = _normalize_title(value)

    if not normalized:
        return []

    return normalized.split()


# ---------------------------------------------------------
# RELEASE NOISE
# ---------------------------------------------------------


_RELEASE_NOISE = {
    "2160p",
    "1080p",
    "720p",
    "576p",
    "480p",
    "360p",
    "240p",
    "4k",
    "uhd",
    "fhd",
    "hd",
    "web",
    "webrip",
    "webdl",
    "web-dl",
    "bluray",
    "brrip",
    "bdrip",
    "hdrip",
    "dvdrip",
    "hdtv",
    "remux",
    "proper",
    "repack",
    "extended",
    "uncut",
    "complete",
    "multi",
    "dual",
    "audio",
    "dubbed",
    "subbed",
    "subs",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "avc",
    "av1",
    "aac",
    "ac3",
    "ddp",
    "dd",
    "atmos",
    "dts",
    "truehd",
    "10bit",
    "8bit",
    "hdr",
    "hdr10",
    "hdr10+",
    "dolby",
    "vision",
    "dv",
}


def _clean_title_tokens(value: str | None) -> list[str]:
    tokens = _title_tokens(value)

    return [
        token
        for token in tokens
        if token not in _RELEASE_NOISE
        and not re.fullmatch(r"\d{3,4}p", token)
        and not re.fullmatch(r"\d{4}", token)
    ]


# ---------------------------------------------------------
# YEAR EXTRACTION
# ---------------------------------------------------------


def _extract_year(value: str | None) -> int | None:
    if not value:
        return None

    match = re.search(
        r"\b(19\d{2}|20\d{2})\b",
        value,
    )

    if not match:
        return None

    try:
        return int(match.group(1))
    except ValueError:
        return None


# ---------------------------------------------------------
# EPISODE DETECTION
# ---------------------------------------------------------


def _episode_matches(
    title: str,
    season: str | int | None,
    episode: str | int | None,
) -> bool:
    """
    Verify that a series release actually contains the
    requested season/episode.

    Accepted:
        S01E01
        S1E1
        1x01
        01x01
    """

    if season is None or episode is None:
        return True

    try:
        season_num = int(season)
        episode_num = int(episode)
    except (TypeError, ValueError):
        return False

    normalized = _normalize_title(title)

    patterns = [
        rf"\bs{season_num:02d}e{episode_num:02d}\b",
        rf"\bs{season_num}e{episode_num}\b",
        rf"\bs{season_num:02d}e{episode_num}\b",
        rf"\b{season_num:02d}x{episode_num:02d}\b",
        rf"\b{season_num}x{episode_num:02d}\b",
        rf"\b{season_num}x{episode_num}\b",
    ]

    return any(
        re.search(
            pattern,
            normalized,
            re.IGNORECASE,
        )
        for pattern in patterns
    )


# ---------------------------------------------------------
# TITLE MATCHING - MOVIES
# ---------------------------------------------------------


def _title_matches_movie(
    requested_title: str,
    result_title: str,
    requested_year: int | None = None,
) -> bool:
    """
    Strict movie release matching.

    The requested movie title must appear at the beginning
    of the release title.

    Examples:

        Cars 2006 1080p BluRay
            -> ACCEPT

        Cars.2006.1080p.x264
            -> ACCEPT

        Cars (2006) WEB-DL
            -> ACCEPT

        Cars 2 2011
            -> REJECT

        Cars 3 2017
            -> REJECT

        Counting Cars 2018
            -> REJECT

        Project Cars 2
            -> REJECT

        Classic Cars
            -> REJECT

        Used Cars
            -> REJECT

        Cars on the Road
            -> REJECT

        Cars That Ate Paris
            -> REJECT
    """

    requested_tokens = _clean_title_tokens(requested_title)
    result_tokens = _title_tokens(result_title)

    if not requested_tokens or not result_tokens:
        return False

    requested_len = len(requested_tokens)

    # -----------------------------------------------------
    # TITLE MUST START THE RELEASE
    # -----------------------------------------------------

    if len(result_tokens) < requested_len:
        return False

    if result_tokens[:requested_len] != requested_tokens:
        return False

    # -----------------------------------------------------
    # NOTHING AFTER THE TITLE
    # -----------------------------------------------------

    remaining = result_tokens[requested_len:]

    if not remaining:
        return True

    # -----------------------------------------------------
    # NUMBERED SEQUELS
    # -----------------------------------------------------

    if re.fullmatch(r"\d{1,2}", remaining[0]):
        return False

    # -----------------------------------------------------
    # YEAR
    # -----------------------------------------------------

    if re.fullmatch(
        r"(19\d{2}|20\d{2})",
        remaining[0],
    ):
        release_year = int(remaining[0])

        if (
            requested_year is not None
            and release_year != requested_year
        ):
            return False

        remaining = remaining[1:]

    # -----------------------------------------------------
    # RELEASE METADATA
    # -----------------------------------------------------

    metadata_started = False

    for token in remaining:

        # Standard release metadata.
        if token in _RELEASE_NOISE:
            metadata_started = True
            continue

        # Resolution.
        if re.fullmatch(
            r"\d{3,4}p",
            token,
        ):
            metadata_started = True
            continue

        # Bit depth.
        if re.fullmatch(
            r"\d{1,2}bit",
            token,
        ):
            metadata_started = True
            continue

        # Year appearing later in a release.
        if re.fullmatch(
            r"\d{4}",
            token,
        ):
            if requested_year is not None:
                try:
                    if int(token) != requested_year:
                        return False
                except ValueError:
                    return False

            metadata_started = True
            continue

        # Common release/source identifiers.
        if token in {
            "amzn",
            "nf",
            "nfweb",
            "hmax",
            "max",
            "dsnp",
            "atvp",
            "pmtp",
            "cr",
            "bbc",
            "it",
            "us",
            "uk",
            "multi",
            "subs",
            "dub",
            "eng",
            "ger",
            "fre",
            "spa",
            "ita",
            "jpn",
            "kor",
            "chs",
            "cht",
        }:
            metadata_started = True
            continue

        # Once metadata has started, tolerate unknown
        # release-group / technical tokens.
        if metadata_started:
            continue

        # Anything else before metadata starts is considered
        # part of another title.
        return False

    # -----------------------------------------------------
    # FINAL YEAR VALIDATION
    # -----------------------------------------------------

    if requested_year is not None:
        result_year = _extract_year(result_title)

        if (
            result_year is not None
            and result_year != requested_year
        ):
            return False

    return True


# ---------------------------------------------------------
# TITLE MATCHING - SERIES
# ---------------------------------------------------------


def _title_matches_series(
    requested_title: str,
    result_title: str,
) -> bool:
    """
    Strict series title matching.

    The requested show title must occur at the beginning
    of the release title.

    Examples:

        Breaking Bad S01E01 1080p
            -> ACCEPT

        The Office US S01E01 WEB-DL
            -> ACCEPT

        Counting Cars S01E01
            -> REJECT when requesting Cars

        Monarch Legacy of Monsters S01E01
            -> REJECT when requesting Monster
    """

    requested_tokens = _clean_title_tokens(requested_title)
    result_tokens = _title_tokens(result_title)

    if not requested_tokens or not result_tokens:
        return False

    requested_len = len(requested_tokens)

    if len(result_tokens) < requested_len:
        return False

    # -----------------------------------------------------
    # Requested series title MUST START the release.
    # -----------------------------------------------------

    if result_tokens[:requested_len] != requested_tokens:
        return False

    # -----------------------------------------------------
    # After the show title, allow normal series metadata.
    # -----------------------------------------------------

    remaining = result_tokens[requested_len:]

    if not remaining:
        return True

    metadata_started = False

    for token in remaining:

        # Season/episode token.
        if re.fullmatch(
            r"s\d{1,2}e\d{1,3}",
            token,
            re.IGNORECASE,
        ):
            metadata_started = True
            continue

        # Alternate season/episode format.
        if re.fullmatch(
            r"\d{1,2}x\d{1,3}",
            token,
            re.IGNORECASE,
        ):
            metadata_started = True
            continue

        # Resolution.
        if re.fullmatch(
            r"\d{3,4}p",
            token,
        ):
            metadata_started = True
            continue

        # Year.
        if re.fullmatch(
            r"(19\d{2}|20\d{2})",
            token,
        ):
            metadata_started = True
            continue

        # Standard release metadata.
        if token in _RELEASE_NOISE:
            metadata_started = True
            continue

        # Common release/source identifiers.
        if token in {
            "amzn",
            "nf",
            "nfweb",
            "hmax",
            "max",
            "dsnp",
            "atvp",
            "pmtp",
            "bbc",
            "multi",
            "subs",
            "dub",
            "eng",
            "ger",
            "fre",
            "spa",
            "ita",
            "jpn",
            "kor",
            "chs",
            "cht",
        }:
            metadata_started = True
            continue

        # Once metadata has started, tolerate unknown
        # release group / technical tokens.
        if metadata_started:
            continue

        # Anything else is part of another title.
        return False

    return True


# ---------------------------------------------------------
# RESULT FILTERING
# ---------------------------------------------------------


# Sources that look results up by IMDb ID, so a release they return is for
# the requested item even when its name is a localized title.
ID_BACKED_SOURCES = {"comet", "mediafusion", "zilean", "eztv"}

_EPISODE_MARKER = re.compile(
    r"\bs\d{1,2}e\d{1,3}\b|\b\d{1,2}x\d{2}\b|\bseason\b|\btemporada\b",
    re.IGNORECASE,
)

_MAX_ALIASES = 10


def _candidate_titles(query: str, aliases) -> list[str]:
    """The requested title plus usable alternate titles, without repeats."""

    titles = [query]

    for alias in aliases or []:
        if isinstance(alias, dict):
            alias = alias.get("title") or alias.get("name")

        if isinstance(alias, str) and alias.strip() and alias.strip() not in titles:
            titles.append(alias.strip())

        if len(titles) > _MAX_ALIASES:
            break

    return titles


def _is_localized_release_of_request(
    result: TorrentResult,
    result_title: str,
    media_type: str | None,
    season: str | None,
    episode: str | None,
    year: int | None,
) -> bool:
    """
    Accept a release whose name doesn't match the (English) title when it
    is very likely a localized release of the requested item: it came from
    an IMDb-ID-backed source, carries a non-English language tag, and its
    year (movies) or season/episode (series) matches.

    Latino/Spanish releases, for example, are usually named in Spanish:
    "El Padrino 1972 1080p Latino" for The Godfather. Requiring a language
    tag keeps the cases the strict check exists for rejected, e.g. an
    English "Monarch Legacy of Monsters S01E01" returned for "Monster".
    """

    if getattr(result, "source", "") not in ID_BACKED_SOURCES:
        return False

    languages = detect_languages(result_title) - NON_LANGUAGE_TAGS - {"english"}
    if not languages:
        return False

    if media_type == "movie":
        if not year or _EPISODE_MARKER.search(result_title):
            return False

        release_year = _extract_year(result_title)
        # Release years are sometimes off by one from the catalogue year.
        return release_year is not None and abs(release_year - year) <= 1

    if media_type == "series":
        return (
            season is not None
            and episode is not None
            and _episode_matches(result_title, season, episode)
        )

    return False


def result_matches_request(
    result: TorrentResult,
    query: str,
    media_type: str | None,
    season: str | None,
    episode: str | None,
    *,
    aliases=None,
    year: int | None = None,
) -> bool:
    """
    Final safety filter applied after every scraper returns.

    IMPORTANT:
        IMDb-ID-backed sources such as Comet and MediaFusion
        are NOT automatically trusted.

    An IMDb ID identifies the requested media item when
    searching the source, but the returned release title
    still has to pass our local title/media/episode filter.

    This prevents cases such as:

        Supergirl movie
            -> Supergirl S01E01
            -> REJECT

        Monster anime
            -> Monarch Legacy of Monsters S01E01
            -> REJECT

    The title may match the requested title or any of its ``aliases``
    (alternate titles from Cinemeta). Localized releases from ID-backed
    sources get one narrow exception: see _is_localized_release_of_request.
    """

    result_title = str(
        getattr(result, "title", "") or ""
    )

    if not result_title:
        return False

    titles = _candidate_titles(query, aliases)

    # -----------------------------------------------------
    # SERIES
    # -----------------------------------------------------

    if media_type == "series":
        if not any(
            _title_matches_series(title, result_title)
            for title in titles
        ):
            if _is_localized_release_of_request(
                result, result_title, media_type, season, episode, year
            ):
                logger.debug("LOCALIZED ACCEPT [series]: %r", result_title)
                return True

            logger.debug(
                "TITLE FILTER REJECT [series]: %r -> %r",
                query,
                result_title,
            )
            return False

        if not _episode_matches(
            result_title,
            season,
            episode,
        ):
            logger.debug(
                "EPISODE FILTER REJECT: S%sE%s -> %r",
                season,
                episode,
                result_title,
            )
            return False

        return True

    # -----------------------------------------------------
    # MOVIE
    # -----------------------------------------------------

    if media_type == "movie":
        if not any(
            _title_matches_movie(
                title,
                result_title,
                requested_year=_extract_year(title),
            )
            for title in titles
        ):
            if _is_localized_release_of_request(
                result, result_title, media_type, season, episode, year
            ):
                logger.debug("LOCALIZED ACCEPT [movie]: %r", result_title)
                return True

            logger.debug(
                "TITLE FILTER REJECT [movie]: %r -> %r",
                query,
                result_title,
            )
            return False

        return True

    # -----------------------------------------------------
    # UNKNOWN MEDIA TYPE
    # -----------------------------------------------------

    return True


# Backwards-compatible alias for the old private name.
_result_matches_request = result_matches_request
