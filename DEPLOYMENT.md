# Cauldron Deployment Options

Cauldron now supports multiple deployment profiles to streamline the container setup based on your needs.

## Deployment Profiles

### 1. Core Setup (Minimal) - 2 Containers
**Best for:** Basic functionality, resource-constrained environments, testing

```bash
docker compose up -d
```

**Containers:**
- `app` - Main Cauldron application
- `redis` - Cache layer (optional, app has in-memory fallback)

**Features:**
- All core scraping and filtering functionality
- Redis caching for performance
- No Zilean DMM enhancement
- Minimal resource usage

### 2. Full Setup (Enhanced) - 4 Containers
**Best for:** Production use, maximum quality results

```bash
docker compose --profile full up -d
```

**Containers:**
- `app` - Main Cauldron application
- `redis` - Cache layer
- `zilean` - DMM hash-list metadata indexer
- `zilean-postgres` - PostgreSQL for Zilean

**Features:**
- All core functionality
- Redis caching
- Zilean DMM enhancement for better quality matching
- Higher resource usage but better results

The full profile builds Zilean from `./zilean`, which is not part of this
repository: check out the Zilean source there first. To always start the full
stack, set `COMPOSE_PROFILES=full` in `.env`.

### Host-specific overrides

`docker-compose.yml` is kept portable. Anything specific to one server goes in
`docker-compose.override.yml`, which Compose merges automatically and git
ignores. Start from the example:

```bash
cp docker-compose.override.example.yml docker-compose.override.yml
```

The example publishes the app on `127.0.0.1:8008` and joins the external
`npm_default` network used by Nginx Proxy Manager.

### Image-based deploys

The app service runs the image that CI publishes to
`ghcr.io/wizaarddlabs/cauldron` (public, linux/amd64). Choose the tag with
`CAULDRON_VERSION` in `.env`: `latest` follows `main`; pin a release such as
`0.5.1` to upgrade only when you change it. To update:

```bash
docker compose pull app
docker compose up -d
```

A `git pull` is only needed when the compose files themselves change. Don't
bind-mount `./app` into the container: it would replace the image's code with
whatever is checked out on the host. To run local changes instead, build the
checkout with `docker compose up -d --build`.

### Upgrading an existing deployment

On a server that used the old all-in-one compose file, run the upgrade script
right after pulling. It performs the steps below, never overwrites existing
settings, and is safe to re-run:

```bash
git pull
./scripts/upgrade-vps.sh            # add --dry-run to skip the restart
```

It recovers the previous `ADDON_URL` from git history (or pass it as an
argument). The manual equivalent is:

1. Create `docker-compose.override.yml` as above (adjust port/network).
2. Make sure `.env` sets `ADDON_URL` (and `ADMIN_API_KEY` if you use shared
   ranking settings) — these are no longer hardcoded in `docker-compose.yml`.
3. If you run Zilean, add `COMPOSE_PROFILES=full` to `.env`.
4. Pull and restart: `docker compose pull app && docker compose up -d`.
5. If an older override still bind-mounts `./app:/srv/app`, remove that line.

The image now runs as an unprivileged `cauldron` user (uid 10001). On start the
entrypoint takes ownership of `/data`, `cauldron.db*`, `cauldron.key` and
`ranking_preferences.json`; it does not touch other directories such as
`data/zilean-postgres`.

## Environment Variables

### Core Setup Variables
```bash
ADDON_URL=https://your-domain.com
TORRIN_API_KEY=your_torrin_key  # Optional
ADMIN_API_KEY=choose_a_long_random_value  # Enables shared ranking settings writes
CAULDRON_BIND=127.0.0.1  # Host interface the app is published on
CAULDRON_PORT=8000       # Host port
```

### Full Setup Additional Variables
```bash
COMPOSE_PROFILES=full
ZILEAN_ENABLED=true
ZILEAN_POSTGRES_PASSWORD=secure_password
GITHUB_TOKEN=your_github_token  # For DMM hashlists
```

## Resource Requirements

### Core Setup
- **Memory:** ~200MB (app) + ~100MB (redis) = ~300MB
- **Disk:** ~100MB for application + cache data
- **CPU:** Minimal

### Full Setup
- **Memory:** ~200MB (app) + ~100MB (redis) + ~500MB (zilean) + ~100MB (postgres) = ~900MB
- **Disk:** ~100MB app + ~500MB zilean data + cache data
- **CPU:** Moderate (Zilean does background processing)

## Scaling Considerations

- **Start with Core setup** if you're unsure about resource requirements
- **Upgrade to Full setup** if you need better quality matching or have resources available
- **Both setups** can be switched between by changing the profile flag

## Performance Impact

**Without Zilean (Core):**
- Quality matching relies on torrent title analysis only
- May miss some high-quality releases that don't have clear titles
- Faster startup and lower resource usage

**With Zilean (Full):**
- Uses DMM hash-list metadata for quality detection
- Better identification of high-quality releases (REMUX, proper encoding, etc.)
- Slower startup and higher resource usage
- Better long-term quality of results

## Migration

To switch from Core to Full setup:

1. Stop current setup: `docker compose down`
2. Set environment variables for Zilean
3. Start with full profile: `docker compose --profile full up -d`

To switch from Full to Core setup:

1. Stop current setup: `docker compose down`
2. Remove `COMPOSE_PROFILES=full` from `.env` (if set) and set `ZILEAN_ENABLED=false`
3. Start the core stack: `docker compose up -d`
4. (Optional) Remove Zilean data: `rm -rf data/zilean-postgres` (careful, irreversible!)
