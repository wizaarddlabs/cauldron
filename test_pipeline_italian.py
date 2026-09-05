#!/usr/bin/env python3
"""Test Italian filtering through the full pipeline"""
import sys
sys.path.insert(0, '.')

from app.filtering.pipeline import FilterPipeline
from app.models import TorrentResult

def test_italian_required():
    """Test Italian as required language through full pipeline"""

    # Test torrents with various languages
    torrents = [
        TorrentResult(title='Movie [Italian] 1080p', info_hash='a'*40, magnet='mag', source='scraper', seeders=100),
        TorrentResult(title='Film [Italiano] 1080p', info_hash='b'*40, magnet='m2', source='scraper', seeders=100),
        TorrentResult(title='Movie [English] 1080p', info_hash='c'*40, magnet='m3', source='scraper', seeders=100),
        TorrentResult(title='Film [Français] 1080p', info_hash='d'*40, magnet='m4', source='scraper', seeders=100),
        TorrentResult(title='Pelicula [Español] 1080p', info_hash='e'*40, magnet='m5', source='scraper', seeders=100),
        TorrentResult(title='Movie 1080p', info_hash='f'*40, magnet='m6', source='scraper', seeders=100),
        TorrentResult(title='Movie.Ita.Eng.1080p', info_hash='g'*40, magnet='m7', source='scraper', seeders=100),
    ]

    # Test with Italian as required language
    pipeline = FilterPipeline({'required_languages': ['italian']})
    results = pipeline.apply(torrents)

    print("Test: Italian as required language")
    print(f"Input: {len(torrents)} torrents")
    print(f"Expected: 3 (Italian, Italiano, Ita)")
    print(f"Got: {len(results)} torrents")
    print(f"Results: {[t.title for t in results]}")

    if len(results) == 3:
        print("✅ PASS")
    else:
        print("❌ FAIL")

    # Test with empty required_languages (should return all)
    pipeline_empty = FilterPipeline({'required_languages': []})
    results_empty = pipeline_empty.apply(torrents)

    print(f"\nTest: Empty required_languages")
    print(f"Input: {len(torrents)} torrents")
    print(f"Expected: {len(torrents)} (all)")
    print(f"Got: {len(results_empty)} torrents")

    if len(results_empty) == len(torrents):
        print("✅ PASS")
    else:
        print("❌ FAIL")

if __name__ == '__main__':
    test_italian_required()
