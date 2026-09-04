#!/usr/bin/env python3
"""Test Italian language filtering"""
import sys
sys.path.insert(0, '.')

from app.filtering.matchers import matches_required_languages, LANGUAGE_PATTERNS

def test_italian_patterns():
    """Test Italian language patterns"""

    # Test cases
    test_cases = [
        ("Movie [Italian] 1080p", True),
        ("Film [Italiano] 1080p", True),
        ("Movie [ITA] 1080p", True),
        ("Movie [English] 1080p", False),
        ("Film [Français] 1080p", False),
        ("Pelicula [Español] 1080p", False),
        ("Movie 1080p", False),
        ("Movie.Ita.Eng.1080p", True),  # Common pattern
        ("Movie.ITA.1080p", True),
        ("Movie [Ita] 1080p", True),
    ]

    print("Testing Italian language patterns:")
    print(f"Patterns for 'italian': {LANGUAGE_PATTERNS.get('italian')}")
    print()

    for title, expected in test_cases:
        result = matches_required_languages(title, ['italian'])
        status = "✅" if result == expected else "❌"
        print(f"{status} '{title}' -> {result} (expected {expected})")

if __name__ == '__main__':
    test_italian_patterns()
