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
