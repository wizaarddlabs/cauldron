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
