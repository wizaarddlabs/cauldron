"""Language tags vs title words, and the Dubbed / Unknown options."""

import pytest

from app.filtering.matchers import (
    detect_languages,
    matches_excluded_languages,
    matches_language,
    matches_required_languages,
)
from app.filtering.pipeline import FilterPipeline
from app.models import TorrentResult


@pytest.mark.parametrize(
    "title",
    [
        "El Camino 2019 1080p WEB",          # el = Greek code
        "Peter Pan 2003 1080p BluRay",       # pan = Punjabi
        "Ben-Hur 1959 1080p",                # ben = Bengali
        "Por Que Te Vas 2020 1080p",         # por = Portuguese
        "Mar Adentro 2004 1080p",            # mar = Marathi
        "The French Connection 1971 1080p",  # French
        "PETER PAN 2003 1080p",              # all-caps title
    ],
)
def test_title_words_are_not_language_tags(title):
    assert detect_languages(title) == set()
    assert matches_excluded_languages(title, ["greek", "punjabi", "bengali", "portuguese", "marathi", "french"])


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Movie.2024.SPA.LAT.1080p", {"spanish", "latino"}),
        ("Pelicula [Latino] 1080p", {"latino"}),
        ("El.Padrino.1972.1080p.Latino", {"latino"}),
        ("Movie 2024 1080p Dual Latino-Ingles", {"latino", "multi"}),
        ("Film 2023 iTA ENG 1080p", {"italian", "english"}),
        ("Movie.Ita.Eng.1080p", {"italian", "english"}),
        ("Show S01E02 [ITA] 720p", {"italian"}),
        ("Movie 2024 Dubbed 1080p", {"dubbed"}),
        ("Pelicula 2024 1080p Doblado", {"dubbed"}),
    ],
)
def test_release_tags_are_detected(title, expected):
    assert detect_languages(title) == expected


def test_unknown_matches_untagged_releases():
    assert matches_required_languages("Movie.2024.1080p.WEB-DL", ["unknown"])
    assert matches_required_languages("Movie 2024 Dubbed 1080p", ["unknown"])  # dubbed isn't a language
    assert not matches_required_languages("Movie.2024.1080p.FRENCH", ["unknown"])
    assert not matches_required_languages("Movie 2024 1080p MULTi", ["unknown"])


def test_required_english_or_unknown_keeps_untagged_releases():
    # TechFuz's case: requiring English alone drops untagged (usually English) releases.
    assert not matches_required_languages("Rare.Movie.2001.720p", ["english"])
    assert matches_required_languages("Rare.Movie.2001.720p", ["english", "unknown"])


def test_dubbed_and_unknown_can_be_excluded():
    assert not matches_excluded_languages("Movie 2024 Dubbed 1080p", ["dubbed"])
    assert not matches_excluded_languages("Movie.2024.1080p.WEB", ["unknown"])
    assert matches_excluded_languages("Movie.2024.1080p.ENG", ["unknown"])


def test_english_filter_accepts_english_tagged_releases():
    # Previously "english" itself counted as a foreign pattern.
    assert matches_language("Movie 2024 1080p English", ["english"])
    assert matches_language("Movie 2024 1080p MULTi", ["english"])
    assert not matches_language("Movie 2024 1080p FRENCH", ["english"])


def test_pipeline_required_latino():
    torrents = [
        TorrentResult(title=t, info_hash=c * 40, magnet="m", source="s", seeders=5)
        for t, c in [("Movie 2024 1080p Latino", "a"), ("Movie 2024 1080p", "b"), ("El Movie 2024 1080p", "c")]
    ]

    kept = FilterPipeline({"required_languages": ["latino"]}).apply(torrents)

    assert [t.title for t in kept] == ["Movie 2024 1080p Latino"]
