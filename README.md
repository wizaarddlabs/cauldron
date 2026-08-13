# 🧙🏻‍♂️ Cauldron

**A modular, open-source torrent & debrid aggregation engine for Stremio.**

Cauldron searches multiple torrent sources, validates results against the requested movie or series, checks cache availability where supported, ranks results according to user preferences, and resolves selected torrents through a configured debrid provider.

Cauldron can be used as:

* A **Stremio addon** — generate a personal addon URL containing your provider configuration and install it directly into Stremio.
* A **standalone REST API** — use `/api/search`, `/api/availability`, and `/api/resolve` from your own applications, scripts, or frontend.
* A **modular aggregation engine** — add torrent sources, debrid providers, cache providers, and ranking behavior without changing the core application.

---

## How It Works

```text
                         ┌─────────────────────┐
                         │      Stremio        │
                         │     / Your App      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Cauldron API     │
                         │      FastAPI        │
                         └──────────┬──────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                                   │
                  ▼                                   ▼
          Public Scrapers                           Zilean
          TPB / 1337x /                            Optional
          YTS / Nyaa /                               │
          EZTV / etc.                                │
                  │                                  │
                  └─────────────────┼────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │  Title / Episode    │
                         │      Filtering      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Deduplication     │
                         │     by InfoHash     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Cache Availability  │
                         │  where supported    │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ User-Selected       │
                         │      Sorting        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Debrid Provider   │
                         │ RD / AD / PM / TB   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Direct Playback URL │
                         └─────────────────────┘
```

---

# Features

### 🔎 Multi-source torrent aggregation

Cauldron can search multiple public and API-backed torrent sources concurrently.

Current sources include:

* The Pirate Bay
* 1337x
* YTS
* Nyaa
* EZTV
* Bitsearch
* Torrin
* Zilean *(optional/self-hosted)*

The scraper architecture is modular, so additional sources can be added without changing the API layer.

### 🎯 Strict result validation

Public torrent indexes frequently return results that are only loosely related to the requested title.

Cauldron therefore applies a strict validation layer after scraping.

For movies, Cauldron validates:

* The requested title starts the release title.
* Numbered sequels are rejected when they do not match the requested movie.
* Unrelated titles containing the requested title are rejected.
* Release metadata is tolerated after the title.
* Requested years are validated when available.

For series, Cauldron validates:

* The requested series title starts the release title.
* Season/episode information is validated.
* `S01E01`, `S1E1`, `1x01`, and similar formats are supported.
* Unrelated titles containing the requested title are rejected.

For example, a request for:

```text
Cars
```

will not incorrectly return:

```text
Counting Cars
Project Cars
Classic Cars
Used Cars
Cars 2
Cars 3
```

Likewise, a request for a specific series episode will not accept a release for another episode simply because the show title matches.

---

# Concurrent Scraping

Registered scrapers are queried concurrently.

```python
tasks = [
    _safe_search(
        scraper,
        query,
        imdb_id,
        season,
        episode,
        media_type,
    )
    for scraper in _SCRAPERS
]

results_per_scraper = await asyncio.gather(*tasks)
```

A failure in one scraper does not prevent the remaining sources from returning results.

Each scraper is isolated through a safe wrapper that logs failures and returns an empty result set instead of taking down the entire search.

--

# Result Deduplication

After all scrapers finish, Cauldron deduplicates results using the torrent's info hash.

```text
Scraper A ──┐
Scraper B ──┼──► Filter ──► Deduplicate ──► Sort
Torrin ─────┘
```

If the same info hash is returned by multiple sources, Cauldron keeps a single result.

When duplicate results have different seeder counts, the version with the greater number of seeders is retained.

Results without an info hash are retained using a fallback key based on their title and magnet.

---

# Cache Checking

Cauldron can associate torrent results with cache availability where a cache-checking service or provider supports it.

Cache information is exposed to the Stremio result as:

```text
⚡ Cached
```

or:

```text
⏳ Uncached
```

Cache checking is intentionally treated as separate from debrid resolution.

This is important because not every debrid provider exposes a native torrent cache-check endpoint.

Cauldron can therefore use external/community cache information where available without assuming that every debrid provider supports direct cache queries.

Cache status is also available to the sorting system.

---

# User-Controlled Sorting

Cauldron's sorting system is **priority-based**.

The order selected by the user determines the order of importance.

For example:

```text
Cache Status
Resolution
Seeders
Quality Score
Size
```

means:

1. Cached results come first.
2. Within the same cache status, higher resolution comes first.
3. Within the same resolution, results with more seeders come first.
4. Quality score is then used as a tiebreaker.
5. Size is used as the final tiebreaker.

This is **not** an arbitrary weighted score.

The selected criteria are evaluated lexicographically in the exact order provided by the UI.

For example:

```text
["cached", "resolution", "seeders", "quality", "size"]
```

produces a priority tuple equivalent to:

```text
Cached
  ↓
Resolution
  ↓
Seeders
  ↓
Quality
  ↓
Size
```

Therefore a cached 1080p release with 325 seeds will rank above an uncached 1080p release with 2,369 seeds when **Cache Status** is the first selected criterion.

If the user instead chooses:

```text
["resolution", "seeders", "cached"]
```

then resolution is the primary criterion, seeders are the secondary criterion, and cache status is only used after those.

This allows the Stremio configuration UI to directly control result ordering.

### Supported sorting criteria

* **Cache Status**
* **Resolution**
* **Seeders**
* **Quality Score**
* **Size**
* **Leechers**

Aliases such as `cache`, `cached`, `cache_status`, and `Cache Status` are normalized internally.

---

# Supported Debrid Providers

Cauldron currently supports:

* Real-Debrid
* AllDebrid
* Premiumize
* TorBox

Adding another provider requires implementing the `DebridClient` interface in:

```text
app/debrid/base.py
```

and registering the provider in:

```text
app/debrid/factory.py
```

---

# Quick Start — Docker

```bash
git clone <your-repo-url>
cd cauldron

cp .env.example .env

docker compose up -d
```

The API will be available at:

```text
http://localhost:8000
```

The Docker deployment includes the services required by the enabled Cauldron features.

Optional services such as Zilean can be enabled through the environment configuration.

---

# Installing as a Stremio Addon

Cauldron generates a personal configuration segment containing the selected debrid provider and API key.

The configuration is encoded into the addon URL rather than being stored in a central Cauldron database.

Generate a configuration with:

### Real-Debrid

```bash
python scripts/make_config.py realdebrid YOUR_RD_API_KEY
```

### AllDebrid

```bash
python scripts/make_config.py alldebrid YOUR_AD_API_KEY
```

### Premiumize

```bash
python scripts/make_config.py premiumize YOUR_PM_API_KEY
```

### TorBox

```bash
python scripts/make_config.py torbox YOUR_TB_API_KEY
```

The script produces an addon URL similar to:

```text
http://localhost:8000/<config>/manifest.json
```

Paste the generated URL into Stremio's:

**Add addon → Add addon via URL**

---

# REST API

## Search

Search across all enabled sources:

```bash
curl "http://localhost:8000/api/search?q=your+query"
```

---

## Availability

Check availability through a supported provider:

```bash
curl "http://localhost:8000/api/availability?q=your+query&provider=alldebrid&api_key=YOUR_KEY"
```

---

## Resolve

Resolve a magnet to a direct playback URL:

```bash
curl -X POST http://localhost:8000/api/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "alldebrid",
    "api_key": "YOUR_KEY",
    "magnet": "magnet:?xt=urn:btih:..."
  }'
```

---

# API Documentation

FastAPI's interactive Swagger documentation is available at:

```text
http://localhost:8000/docs
```

OpenAPI schema:

```text
http://localhost:8000/openapi.json
```

---

# Local Development

Without Docker:

```bash
python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

uvicorn app.main:app --reload
```

---

# Project Layout

```text
app/
├── main.py
├── config.py
├── models.py
│
├── api/
│   ├── routes.py
│   └── stremio.py
│
├── scrapers/
│   ├── base.py
│   ├── public_scraper.py
│   ├── torrin.py
│   └── aggregator.py
│
├── filtering/
│   └── sorting.py
│
├── ranking/
│   ├── preferences.py
│   └── scorer.py
│
├── debrid/
│   ├── base.py
│   ├── realdebrid.py
│   ├── alldebrid.py
│   ├── premiumize.py
│   ├── torbox.py
│   └── factory.py
│
└── cache/
    └── store.py
```

---

# Architecture

### `app/api/`

Contains the external API surface.

```text
routes.py
```

Provides the REST API:

```text
/api/search
/api/availability
/api/resolve
```

```text
stremio.py
```

Implements the Stremio addon protocol:

```text
/manifest.json
/stream/...
```

It is responsible for converting Cauldron results into Stremio-compatible streams and playback URLs.

---

### `app/scrapers/`

Contains torrent sources.

```text
base.py
```

Defines the scraper interface.

```text
public_scraper.py
```

Contains the built-in public torrent source integrations.

```text
torrin.py
```

Provides Torrin integration.

```text
aggregator.py
```

Runs registered scrapers concurrently, applies strict result validation, deduplicates results, and hands the final set to the ranking/sorting pipeline.

---

### `app/filtering/`

Contains result filtering and sorting logic.

```text
sorting.py
```

Controls the final ordering of torrent results based on the user's selected criteria.

The sorting criteria are positional rather than weighted.

---

### `app/ranking/`

Contains ranking preferences and quality scoring.

```text
preferences.py
```

Stores user-selected ranking preferences.

```text
scorer.py
```

Provides quality/ranking calculations used by the ranking system.

---

### `app/debrid/`

Contains debrid provider implementations.

Each provider implements the common `DebridClient` interface.

---

### `app/cache/`

Contains local caching functionality.

Redis can be used as the backing store, with an in-memory fallback when Redis is unavailable.

---

# Extending Cauldron

## Add a Torrent Source

Create a scraper implementing the `Scraper` interface:

```text
app/scrapers/base.py
```

Then register it in:

```text
app/scrapers/aggregator.py
```

The scraper should return `TorrentResult` objects.

Once registered, its results automatically participate in:

* Concurrent searching
* Title filtering
* Episode validation
* Deduplication
* Cache processing
* Sorting
* Ranking

---

## Add a Debrid Provider

Implement the `DebridClient` interface:

```text
app/debrid/base.py
```

Then:

1. Create the provider implementation.
2. Register it in `app/debrid/factory.py`.
3. Add the provider to the `DebridProvider` enum in `app/models.py`.
4. Add any required configuration variables to `.env.example`.
5. Add configuration generation support if required by the Stremio addon.

---

# Configuration

Cauldron is configured through environment variables.

Copy the example configuration:

```bash
cp .env.example .env
```

Important optional integrations include:

```text
BITSEARCH_ENABLED
ZILEAN_ENABLED
ZILEAN_URL
TORRIN_API_KEY
TORRIN_API_BASE
```

Refer to `.env.example` for the complete current configuration.

---

# Optional Zilean Integration

Zilean can be used as an optional metadata/hash source.

When enabled, Cauldron queries Zilean using movie and series IMDb IDs.

The bundled Zilean and PostgreSQL services are intended to remain on Cauldron's private Docker network rather than being exposed directly to the host.

Enable or disable Zilean with:

```text
ZILEAN_ENABLED=true
```

or:

```text
ZILEAN_ENABLED=false
```

Zilean remains disabled by default in `.env.example`.

---

# Optional Bitsearch Integration

Bitsearch can be enabled or disabled independently:

```text
BITSEARCH_ENABLED=true
```

Bitsearch uses a small local cache to reduce repeated requests and respect its request allowance.

---

# Sources Searched

Cauldron can aggregate results from the following sources:

* **The Pirate Bay** — public torrent search.
* **1337x** — public torrent search.
* **YTS** — movie-focused API search.
* **Nyaa** — anime-focused public search.
* **EZTV** — series-focused API search.
* **Bitsearch** — API-backed search with local request caching.
* **Torrin** — Torrin aggregation/search integration.
* **Zilean** *(optional)* — self-hosted hash-list metadata source.

Not every source is enabled in every deployment.

Individual integrations can be controlled through the corresponding environment variables.

Regardless of source, returned results pass through Cauldron's validation pipeline before being presented to Stremio.

---

# Result Processing Pipeline

For a typical Stremio request, Cauldron processes results in this order:

```text
1. Receive Stremio request
             │
             ▼
2. Determine movie / series / episode
             │
             ▼
3. Query registered scrapers concurrently
             │
             ▼
4. Collect raw TorrentResult objects
             │
             ▼
5. Validate title
             │
             ▼
6. Validate season / episode
             │
             ▼
7. Deduplicate by info hash
             │
             ▼
8. Determine cache status where available
             │
             ▼
9. Apply user's sorting priorities
             │
             ▼
10. Generate Stremio stream entries
             │
             ▼
11. Resolve selected torrent through debrid
             │
             ▼
12. Return direct playback URL
```

This separation keeps source searching, validation, cache checking, ranking, and playback resolution independent.

---

# Legal Note

Cauldron is infrastructure software.

It searches publicly available torrent indexes and interfaces with debrid services using accounts and API credentials supplied by the user.

No media content is hosted by Cauldron itself.

The user is responsible for ensuring that their use of Cauldron, the sources it accesses, and any content they retrieve complies with applicable laws and the terms of the services they use.
