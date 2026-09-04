"""Tests for the filtering pipeline."""
import pytest
from app.filtering.pipeline import FilterPipeline
from app.models import TorrentResult


def test_resolution_filter():
    """Test resolution filtering."""
    pipeline = FilterPipeline({"resolution": ["1080p"]})

    torrents = [
        TorrentResult(
            title="Movie.1080p.BluRay",
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            source="test"
        ),
        TorrentResult(
            title="Movie.720p.BluRay",
            info_hash="b" * 40,
            magnet="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            seeders=100,
            source="test"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 1
    assert filtered[0].title == "Movie.1080p.BluRay"


def test_min_seeders_filter():
    """Test minimum seeders filtering."""
    pipeline = FilterPipeline({"min_seeders": 50})

    torrents = [
        TorrentResult(
            title="Movie.1080p",
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            source="test"
        ),
        TorrentResult(
            title="Movie.720p",
            info_hash="b" * 40,
            magnet="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            seeders=10,
            source="test"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 1
    assert filtered[0].seeders == 100


def test_deduplication():
    """Test deduplication by info hash."""
    pipeline = FilterPipeline({"dedupe_streams": True})

    torrents = [
        TorrentResult(
            title="Movie.1080p",
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            source="test"
        ),
        TorrentResult(
            title="Movie.1080p.Different",
            info_hash="a" * 40,  # Same hash
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=200,  # Higher seeders
            source="test2"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 1
    # The pipeline keeps the first encountered, not the one with higher seeders
    # The aggregator handles higher seeder selection during deduplication


def test_max_size_filter():
    """Test maximum size filtering."""
    pipeline = FilterPipeline({"max_size_gb": 2.0})

    torrents = [
        TorrentResult(
            title="Movie.1080p",
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            size_bytes=1 * 1024 * 1024 * 1024,  # 1 GB
            source="test"
        ),
        TorrentResult(
            title="Movie.1080p.Large",
            info_hash="b" * 40,
            magnet="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            seeders=100,
            size_bytes=5 * 1024 * 1024 * 1024,  # 5 GB
            source="test"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 1
    assert filtered[0].size_bytes == 1 * 1024 * 1024 * 1024


def test_language_filter():
    """Test language filtering."""
    pipeline = FilterPipeline({"language": ["english"]})

    torrents = [
        TorrentResult(
            title="Movie.1080p",  # No language specified = assumed English
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            source="test"
        ),
        TorrentResult(
            title="Movie.1080p.French",
            info_hash="b" * 40,
            magnet="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            seeders=100,
            source="test"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 1
    assert filtered[0].title == "Movie.1080p"


def test_max_per_resolution():
    """Test limiting results per resolution."""
    pipeline = FilterPipeline({"max_per_resolution": 2})

    torrents = [
        TorrentResult(
            title="Movie.1080p.v1",
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            source="test"
        ),
        TorrentResult(
            title="Movie.1080p.v2",
            info_hash="b" * 40,
            magnet="magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            seeders=90,
            source="test"
        ),
        TorrentResult(
            title="Movie.1080p.v3",
            info_hash="c" * 40,
            magnet="magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc",
            seeders=80,
            source="test"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 2


def test_empty_pipeline():
    """Test pipeline with no filters."""
    pipeline = FilterPipeline({})

    torrents = [
        TorrentResult(
            title="Movie.1080p",
            info_hash="a" * 40,
            magnet="magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            seeders=100,
            source="test"
        ),
    ]

    filtered = pipeline.apply(torrents)
    assert len(filtered) == 1