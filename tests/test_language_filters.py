"""Italian language filtering (formerly ad-hoc scripts in the repo root)."""

import pytest

from app.filtering.matchers import matches_required_languages
from app.filtering.pipeline import FilterPipeline
from app.models import TorrentResult


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Movie [Italian] 1080p", True),
        ("Film [Italiano] 1080p", True),
        ("Movie [ITA] 1080p", True),
        ("Movie [Ita] 1080p", True),
        ("Movie.Ita.Eng.1080p", True),
        ("Movie.ITA.1080p", True),
        ("Movie [English] 1080p", False),
        ("Film [Français] 1080p", False),
        ("Pelicula [Español] 1080p", False),
        ("Movie 1080p", False),
    ],
)
def test_italian_language_patterns(title, expected):
    assert matches_required_languages(title, ["italian"]) is expected


def _torrent(title, char):
    return TorrentResult(
        title=title,
        info_hash=char * 40,
        magnet=f"magnet:?xt=urn:btih:{char * 40}",
        source="scraper",
        seeders=100,
    )


TORRENTS = [
    _torrent("Movie [Italian] 1080p", "a"),
    _torrent("Film [Italiano] 1080p", "b"),
    _torrent("Movie [English] 1080p", "c"),
    _torrent("Film [Français] 1080p", "d"),
    _torrent("Pelicula [Español] 1080p", "e"),
    _torrent("Movie 1080p", "f"),
    _torrent("Movie.Ita.Eng.1080p", "1"),
]


def test_pipeline_keeps_only_italian_when_required():
    results = FilterPipeline({"required_languages": ["italian"]}).apply(TORRENTS)

    assert [t.title for t in results] == [
        "Movie [Italian] 1080p",
        "Film [Italiano] 1080p",
        "Movie.Ita.Eng.1080p",
    ]


def test_pipeline_keeps_everything_without_required_languages():
    results = FilterPipeline({"required_languages": []}).apply(TORRENTS)

    assert len(results) == len(TORRENTS)
