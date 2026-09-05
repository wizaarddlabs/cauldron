# Cauldron v0.3.0

## 🔧 Improvements

- Added reliable Offcloud file-size lookup with bounded concurrent requests.
- Added strict Offcloud file-index validation for playback resolution.
- Added a working `DISABLE_CACHE` option for minimal deployments.
- Core Docker services now start by default; Zilean remains opt-in via the full profile.
- Added regression coverage for Offcloud and cache behavior.

---
# Cauldron v0.2.1

## 🐛 Fixed

- **Language Filtering Bug**: Fixed required, preferred, and excluded language filters not working correctly
- The general language filter was running before more specific required/excluded filters, causing conflicts
- Now prioritizes required/excluded language filters over the general language filter when both are set

## 🔧 Technical Changes

- Updated `app/filtering/pipeline.py` to skip general language filter when required or excluded languages are set
- Updated UI version to v0.2.1 in `app/web/index.html`

---
# Cauldron v0.2.0

## 🎉 New Features

- **Offcloud Integration**: Added support for Offcloud as a debrid provider
- **Advanced Language Filtering**: Implemented comprehensive language filtering with:
  - Required languages (must contain at least one)
  - Preferred languages (boosts ranking score)
  - Excluded languages (filters out completely)
  - Support for 44+ languages including Arabic, Bengali, Chinese, Hindi, Japanese, Korean, etc.
- **Multi-language Support**: Added pattern matching for multi/dual audio releases

## 🐛 Fixed

- **Deduplicator Bug**: Fixed deduplicator in filtering pipeline to properly handle torrents with missing info_hashes
- Previously, torrents without info_hashes were incorrectly treated as duplicates and filtered out

## 🗑️ Removed

- Removed "scrape debrid account torrents" functionality from UI and backend
- Removed "multi language" checkbox from settings UI (replaced by comprehensive language filtering)
- Cleaned up debrid client `list_user_torrents` methods across all providers

## 🔧 Enhanced

- **Ranking System**: Added preferred language bonuses to scoring algorithm
- **Language Patterns**: Expanded language pattern matching to cover all UI languages
- **Pipeline Filtering**: Enhanced filtering pipeline with three-tier language filtering system

## 📝 Technical Changes

- Updated `app/filtering/matchers.py` with comprehensive language patterns
- Enhanced `app/filtering/pipeline.py` with required/preferred/excluded language filters
- Updated `app/ranking/scorer.py` with language-based scoring
- Removed deprecated `list_user_torrents` methods from debrid clients
- Updated version to 0.2.0 in `app/config.py`
- Restored version display to UI settings page

---

# Cauldron v0.1.1

## 🐛 Fixed

- Fixed TV episodes appearing in movie stream results.
- Fixed unrelated titles appearing in series results when titles partially matched.
- Fixed `Supergirl` movie searches returning `Supergirl` TV series episodes.
- Fixed `Monster` anime searches returning `Monarch: Legacy of Monsters` results.
- Removed the IMDb-backed scraper filtering bypass.
- Comet, MediaFusion, and Zilean results now pass through the same title validation as other scrapers.

## 🔒 Filtering Improvements

- Added consistent movie title validation across all scrapers.
- Added consistent series title validation across all scrapers.
- Enforced season/episode validation for series results.
- Enforced movie year validation.
- Improved rejection of similar or partially matching titles.

## 📝 Logging

- Added debug logging for title-filter rejections.
- Added debug logging for episode-filter rejections.

## 🔧 Changed

- Updated `app/scrapers/aggregator.py`.
