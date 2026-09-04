# Cauldron Deployment Options

Cauldron now supports multiple deployment profiles to streamline the container setup based on your needs.

## Deployment Profiles

### 1. Core Setup (Minimal) - 2 Containers
**Best for:** Basic functionality, resource-constrained environments, testing

```bash
docker-compose --profile core up -d
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
docker-compose --profile full up -d
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

### 3. Backward Compatible (Default)
```bash
docker-compose up -d
```

This runs the full setup (equivalent to `--profile full`) for backward compatibility.

## Environment Variables

### Core Setup Variables
```bash
ADDON_URL=https://your-domain.com
TORRIN_API_KEY=your_torrin_key  # Optional
```

### Full Setup Additional Variables
```bash
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

1. Stop current setup: `docker-compose down`
2. Set environment variables for Zilean
3. Start with full profile: `docker-compose --profile full up -d`

To switch from Full to Core setup:

1. Stop current setup: `docker-compose down`
2. Start with core profile: `docker-compose --profile core up -d`
3. (Optional) Remove Zilean data: `docker volume rm cauldron_redis-data` (careful!)
