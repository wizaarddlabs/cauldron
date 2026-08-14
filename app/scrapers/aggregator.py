import asyncio
import logging
import re

from app.models import TorrentResult
from app.scrapers.base import Scraper
from app.scrapers.public_scraper import PublicScraper
from app.scrapers.comet import CometScraper
from app.scrapers.mediafusion import MediaFusionScraper

from app.ranking.preferences import RankingPreferences
from app.ranking.scorer import rank_results


logger = logging.getLogger(__name__)


_SCRAPERS: list[Scraper] = [
    PublicScraper(),
    CometScraper(),
    MediaFusionScraper(),
]


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
    value = value.replace("'", "")

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


def _result_matches_request(
    result: TorrentResult,
    query: str,
    media_type: str | None,
    season: str | None,
    episode: str | None,
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

    Every scraper therefore passes through the same final
    validation layer.
    """

    result_title = str(
        getattr(result, "title", "") or ""
    )

    if not result_title:
        return False

    # -----------------------------------------------------
    # SERIES
    # -----------------------------------------------------

    if media_type == "series":
        if not _title_matches_series(
            query,
            result_title,
        ):
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
        requested_year = _extract_year(query)

        if not _title_matches_movie(
            query,
            result_title,
            requested_year=requested_year,
        ):
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


# ---------------------------------------------------------
# SAFE SCRAPER
# ---------------------------------------------------------


async def _safe_search(
    scraper: Scraper,
    query: str,
    imdb_id: str | None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
) -> list[TorrentResult]:

    try:
        results = await scraper.search(
            query,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            media_type=media_type,
        )

        logger.info(
            "%s returned %d raw results for %r",
            scraper.name,
            len(results),
            query,
        )

        return results

    except Exception:
        logger.exception(
            "Scraper %s failed",
            scraper.name,
        )

        return []


# ---------------------------------------------------------
# AGGREGATOR
# ---------------------------------------------------------


async def search_all(
    query: str,
    *,
    imdb_id: str | None = None,
    season: str | None = None,
    episode: str | None = None,
    media_type: str | None = None,
    preferences: RankingPreferences | None = None,
) -> list[TorrentResult]:

    logger.info(
        "=== AGGREGATOR SEARCH === query=%r imdb=%r type=%r S%sE%s",
        query,
        imdb_id,
        media_type,
        season,
        episode,
    )

    # -----------------------------------------------------
    # SEARCH ALL SCRAPERS CONCURRENTLY
    # -----------------------------------------------------

    tasks = [
        _safe_search(
            scraper,
            query,
            imdb_id,
            season,
            episode,
            media_type,
        )
        for scraper in _SCRAPERS
    ]

    results_per_scraper = await asyncio.gather(
        *tasks
    )

    raw_count = sum(
        len(results)
        for results in results_per_scraper
    )

    # -----------------------------------------------------
    # TITLE / EPISODE FILTER
    # -----------------------------------------------------

    filtered_results: list[TorrentResult] = []

    for scraper_results in results_per_scraper:
        for result in scraper_results:
            if _result_matches_request(
                result,
                query,
                media_type,
                season,
                episode,
            ):
                filtered_results.append(result)

    logger.info(
        "TITLE FILTER: %d -> %d results",
        raw_count,
        len(filtered_results),
    )

    # -----------------------------------------------------
    # DEDUPLICATION
    # -----------------------------------------------------

    merged: dict[str, TorrentResult] = {}

    for result in filtered_results:
        info_hash = str(
            getattr(
                result,
                "info_hash",
                "",
            )
            or ""
        ).lower()

        # Results without an info hash cannot safely be
        # deduplicated, but should still be retained.
        if not info_hash:
            unique_key = (
                f"nohash:"
                f"{getattr(result, 'title', '')}:"
                f"{getattr(result, 'magnet', '')}"
            )
        else:
            unique_key = info_hash

        existing = merged.get(unique_key)

        if existing is None:
            merged[unique_key] = result
            continue

        # Keep the result with more seeders.
        if (
            (getattr(result, "seeders", None) or 0)
            > (getattr(existing, "seeders", None) or 0)
        ):
            merged[unique_key] = result

    results = list(
        merged.values()
    )

    logger.info(
        "AFTER DEDUPLICATION: %d results",
        len(results),
    )

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

    if preferences:
        results = rank_results(
            results,
            preferences,
        )
    else:
        results = sorted(
            results,
            key=lambda r: getattr(
                r,
                "seeders",
                0,
            )
            or 0,
            reverse=True,
        )

    logger.info(
        "FINAL AGGREGATOR RESULTS: %d",
        len(results),
    )

    return results