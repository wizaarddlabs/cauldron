# Cauldron v0.8.0

Based on feedback from the r/StremioAddons announcement thread (including the ext.to request).

## Improved

- **Spanish/Latino and other localized releases are no longer thrown away.**
  Such releases are often named in their own language ("El Padrino 1972
  Latino" for The Godfather), and the strict title check only knew the
  English title. Results now also match Cinemeta's alternate titles, and
  sources that look up by IMDb ID (Comet, MediaFusion, Zilean, EZTV) may
  return a localized name when the release has a non-English language tag
  and the year (movies) or season/episode (series) matches.
- **Language detection reads release tags, not title words.** Short codes no
  longer match ordinary words: "El Camino" is not Greek, "Peter Pan" is not
  Punjabi, "Ben-Hur" is not Bengali. A language counts when it appears as a
  tag (after the year/resolution/episode, in brackets, in capitals, or next
  to another language code).
- **New language options: Unknown / no language tag, Dubbed**, pinned at the
  top of each list with Multi-audio. Requiring "Unknown" alongside English
  keeps the many untagged (usually English) releases that were dropped
  before.
- **Leechers** is now available as a sort option.
- **New optional Prowlarr source.** Set `PROWLARR_URL` and `PROWLARR_API_KEY`
  and Cauldron searches every indexer enabled in your Prowlarr, e.g. **EXT
  (ext.to)** through Prowlarr's FlareSolverr proxy. `PROWLARR_INDEXER_IDS`
  limits it to chosen indexers.
- Accented titles match unaccented releases (Amélie / Amelie, Pokémon /
  Pokemon).

## Fixed

- The English language filter treated "English" itself as a foreign tag.

## Documentation

- New **Privacy & Security** section in the README, linked from the setup
  page: what is encrypted and redacted, and why self-hosting gives full
  control over your keys.

---

# Cauldron v0.7.1

## Fixed

- "Add another provider" did nothing for anyone who had opened the setup page
  before upgrading. v0.7.0 still loaded `settings.js?v=6`, the same URL as
  v0.6.0, so browsers kept running their cached v0.6.0 script, which has no
  code for that button. Static files (script, stylesheet, logo) are now linked
  with a hash of their contents, so every change gets a new URL automatically.

---

# Cauldron v0.7.0

## New

- **Several debrid providers in one addon.** Add backup providers on the setup
  page, highest priority first. Every search checks all of their caches at the
  same time, and each torrent is streamed through the first provider that has
  it cached (or the first provider if none do). Streams name the provider they
  use, e.g. `Cauldron • Real-Debrid • ⚡ Cached`.
- Optional "Show a stream for each provider" mode lists every provider for
  every torrent instead of only the best one. With "Cached only", providers
  that don't have a torrent cached are left out.
- Each provider's cache check has its own 12-second limit, so one slow or
  failing provider no longer delays or breaks the whole stream list.
- `scripts/make_config.py` accepts several providers:
  `make_config.py realdebrid KEY1 torbox KEY2`.

## Compatibility

- Existing addons keep working unchanged. Their stream links now include the
  provider (`/<id>/playback/<provider>/<hash>`); the old link format still
  works and uses the addon's first provider.
- New configs also store their first provider in the old single-provider
  fields, so rolling back to v0.6.x keeps them working (with that provider only).

---

# Cauldron v0.6.0

## Improved

- Simpler, phone-friendly setup page:
  - One provider dropdown and one API key field replace six separate key
    fields. "None (direct P2P streams)" is an explicit choice and the default.
  - Choosing a debrid provider without entering its key now shows an error
    instead of silently creating a P2P addon.
  - New **Install in Stremio** button opens the Stremio app directly.
  - Language menus are opaque, one option per row, and open in place on phones.
  - Rarely changed sections (quality, codec, sorting, advanced filters) are
    collapsed, roughly halving the page length on phones.
  - Whole option boxes are tappable, every field has a proper label, and the
    create button stays reachable at the bottom of the screen.

## Security

- The finished addon URL is no longer put in the address bar (it was added as
  `?manifest=...`, ending up in browser history). It is shown on the page and
  sent with `Cache-Control: no-store`.
- API key fields are never pre-filled from the shared server settings.
- Addons created as P2P never fall back to the server-wide `TORRIN_API_KEY`.

## Fixed

- `scripts/make_config.py` produced URLs that no longer worked: it built an
  old-style base64 config, but configs are now stored in SQLite and looked up
  by ID. It now saves a real config (including `p2p`) and prints its URL.

## Removed

- The old unstyled `/configure` page; `/configure` now redirects to the setup
  page (Stremio's "Configure" button uses that path).

---

# Cauldron v0.5.2

## Security

- API keys were written to the logs in plain text. httpx logs every outbound
  request at INFO with the full URL, and Premiumize and TorBox take the API key
  as a URL query parameter. The log redaction filter only checked plain-string
  arguments, so it missed httpx's URL objects. Keys and config IDs are now
  masked in these lines too.

  If you run an instance, treat any existing container logs as containing
  your users' debrid API keys.

---

# Cauldron v0.5.1

## Fixed

- The app no longer crashes on start-up when run through `docker-compose.yml`.
  v0.5.0's compose file passes `CORS_ORIGINS=*`, which the settings loader
  tried to parse as JSON. `CORS_ORIGINS` now accepts `*`, a comma-separated
  list or a JSON list.

## Improved

- `docker-compose.yml` runs the published image
  `ghcr.io/wizaarddlabs/cauldron:${CAULDRON_VERSION:-latest}` instead of
  building on the server. `docker compose up -d --build` still builds locally.
- `scripts/upgrade-vps.sh` pulls the image (falling back to a local build) and
  warns if an override still bind-mounts `./app` over the image's code.

---

# Cauldron v0.5.0

## Security

- Config IDs (which grant use of the owner's debrid account) are shortened in
  application and access logs; API keys in provider URLs are masked.
- The Docker image runs as an unprivileged `cauldron` user.

## Improved

- All outbound requests share one pooled HTTP client, so connections are reused.
- The playback URL cache and its locks are pruned and size-capped.
- Quieter logs: debug-level per-result tracing, no `print()` output.
- Large modules split up (`stremio.py`, `aggregator.py`, public scrapers).

## Development

- CI now runs `ruff` and `pytest`, and image publishing waits for them.
- Test/lint dependencies moved to `requirements-dev.txt`.
- `docker-compose.yml` is portable; host-specific settings go in a gitignored
  `docker-compose.override.yml`. Existing servers: run
  `./scripts/upgrade-vps.sh` after pulling (see `DEPLOYMENT.md`).

---

# Cauldron v0.4.0

## Improved

- Added responsive layouts and more touch-friendly controls for mobile users.

---

# Cauldron v0.3.4

## Improved

- Refined sorting controls and applied purple accents throughout the web UI.

---

# Cauldron v0.3.3

## Fixed

- Search cache keys now reflect ranking preferences, so preference changes take effect immediately.

## Docker

- Published images use the `latest`, `0.3.3`, and `v0.3.3` tags on GitHub Container Registry.

---

# Cauldron v0.3.2

## 🔒 Security and Reliability

- Encrypted generated addon configurations at rest and strengthened configuration IDs.
- Protected shared ranking settings with an admin API key.
- Added a POST availability endpoint to keep provider keys out of request URLs.
- Failed Stremio requests explicitly when configured filtering cannot be applied.
- Added Redis readiness reporting and a Docker healthcheck.

---

# Cauldron v0.3.1

## Fixed

- Torrin now uses the documented instant-availability endpoint and correctly maps cached, uncached, and empty-object responses.
- Completed Torrin account torrents are included in searches and shown as cached for the authenticated user.
- Torrin account results are prioritized before filtering caps and preserved during deduplication.
- Added support for `H.265` and `H.264` codec notation from Torrin filenames.
- Series results are episode-filtered before debrid cache checks to reduce latency.
- Added regression coverage for Torrin cache status, account scraping, provider selection, and result ordering.

## Validation

- Full test suite passes: 16 tests.

---

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
