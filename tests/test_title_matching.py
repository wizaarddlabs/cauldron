import logging

from app.models import TorrentResult
from app.scrapers.title_matching import result_matches_request


def _result(title):
    return TorrentResult(
        title=title,
        info_hash="c" * 40,
        magnet="magnet:?xt=urn:btih:" + "c" * 40,
        source="scraper",
    )


def test_movie_match_and_reject(caplog):
    caplog.set_level(logging.DEBUG, logger="app.scrapers.title_matching")

    assert result_matches_request(
        _result("The.Matrix.1999.1080p.BluRay"), "The Matrix", "movie", None, None
    )
    assert not result_matches_request(
        _result("Completely.Different.Film.2010.1080p"), "The Matrix", "movie", None, None
    )
    assert "TITLE FILTER REJECT [movie]" in caplog.text


def test_series_episode_match_and_reject(caplog):
    caplog.set_level(logging.DEBUG, logger="app.scrapers.title_matching")

    assert result_matches_request(
        _result("Severance.S02E03.1080p.WEB"), "Severance", "series", "2", "3"
    )
    assert not result_matches_request(
        _result("Severance.S02E05.1080p.WEB"), "Severance", "series", "2", "3"
    )
    assert "EPISODE FILTER REJECT" in caplog.text


# ---- Localized (e.g. Latino) releases and alternate titles ----

import pytest  # noqa: E402

from app.scrapers.title_matching import result_matches_request as _matches  # noqa: E402


def _r(title, source="comet"):
    return TorrentResult(title=title, info_hash="c" * 40, magnet="m", source=source)


@pytest.mark.parametrize(
    ("title", "query", "media_type", "season", "episode", "year", "source", "expected"),
    [
        # Spanish-titled Latino release from an IMDb-ID source: accepted.
        ("El Padrino 1972 1080p Latino", "The Godfather", "movie", None, None, 1972, "comet", True),
        ("Intensamente 2 2024 1080p Latino", "Inside Out 2", "movie", None, None, 2024, "mediafusion", True),
        # ...but not from a text-search source,
        ("El Padrino 1972 1080p Latino", "The Godfather", "movie", None, None, 1972, "1337x", False),
        # ...nor without a language tag,
        ("El Padrino 1972 1080p", "The Godfather", "movie", None, None, 1972, "comet", False),
        # ...nor with the wrong year,
        ("El Padrino 1990 1080p Latino", "The Godfather", "movie", None, None, 1972, "comet", False),
        # ...nor an episode for a movie request.
        ("Supergirl S01E01 Latino 1080p", "Supergirl", "movie", None, None, 1984, "comet", False),
        # Series: right episode with a language tag.
        ("La Casa de Papel S01E02 1080p SPA", "Money Heist", "series", "1", "2", None, "comet", True),
        ("La Casa de Papel S01E03 1080p SPA", "Money Heist", "series", "1", "2", None, "comet", False),
        # The case the strict check exists for stays rejected.
        ("Monarch Legacy of Monsters S01E01 1080p", "Monster", "series", "1", "1", None, "comet", False),
    ],
)
def test_localized_releases(title, query, media_type, season, episode, year, source, expected):
    assert _matches(_r(title, source), query, media_type, season, episode, year=year) is expected


def test_alternate_titles_and_accents():
    assert _matches(
        _r("Le Fabuleux Destin d'Amelie Poulain 2001 1080p", "1337x"),
        "Amelie", "movie", None, None,
        aliases=["Le Fabuleux Destin d’Amélie Poulain"],
    )
    assert _matches(_r("Pokemon Detective Pikachu 2019 1080p", "yts"), "Pokémon Detective Pikachu", "movie", None, None)
    assert not _matches(_r("Cars 2 2011 1080p", "1337x"), "Cars", "movie", None, None, aliases=["Cars"])
