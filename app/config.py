"""
Application configuration.
All values are overridable via environment variables / .env file.
"""
import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    app_name: str = "Cauldron"
    log_level: str = "INFO"
    addon_id: str = "community.cauldron"
    addon_name: str = "Cauldron"
    addon_version: str = __version__
    addon_url: str = "http://localhost:8000"
    admin_api_key: str | None = Field(
        default=None,
        description="Required to change shared ranking preferences",
    )

    # --- Debrid provider API bases (rarely need changing) ---
    realdebrid_api_base: str = "https://api.real-debrid.com/rest/1.0"
    alldebrid_api_base: str = "https://api.alldebrid.com/v4.1"
    premiumize_api_base: str = "https://www.premiumize.me/api"
    torbox_api_base: str = "https://api.torbox.app/v1/api"
    torrin_api_base: str = "https://api.torrin.app"
    torrin_api_key: str | None = None
    offcloud_api_base: str = "https://offcloud.com/api"
    offcloud_fetch_sizes: bool = True  # Fetch file sizes via HEAD requests (adds latency)
    offcloud_size_cache_ttl: int = 60 * 60  # 1 hour cache for file sizes
    # --- Cache ---
    redis_url: str | None = Field(default=None, description="e.g. redis://localhost:6379/0")
    cache_ttl_search: int = 60 * 60       # 1 hour for scrape results (increased for high-traffic)
    cache_ttl_availability: int = 60 * 15  # 15 min for debrid-cache checks
    redis_max_memory: str = "512mb"      # Redis max memory limit for production
    redis_eviction_policy: str = "allkeys-lru"  # Evict least recently used keys
    disable_cache: bool = False  # Allow running without Redis for minimal setup

    # --- Search behavior ---
    max_results_per_scraper: int = 200  # Soft limit for individual scrapers (can be exceeded)
    scrape_timeout_seconds: int = 20
    httpx_max_connections: int = 100  # Max concurrent connections in the shared HTTP pool
    httpx_max_keepalive_connections: int = 20  # Idle connections kept open for reuse
    bitsearch_enabled: bool = True
    bitsearch_api_base: str = "https://bitsearch.to/api/v1"
    bitsearch_api_key: str | None = None
    bitsearch_cache_ttl_seconds: int = 60 * 60
    # Zilean is a self-hosted, optional index of DMM hash-list metadata.
    zilean_enabled: bool = False
    zilean_url: str = "http://zilean:8181"
    zilean_max_results: int = 100
    # Prowlarr (optional): searches every indexer enabled there, e.g. EXT /
    # ext.to via Prowlarr's FlareSolverr proxy. Disabled unless URL and key
    # are both set.
    prowlarr_url: str | None = None
    prowlarr_api_key: str | None = None
    # Comma-separated Prowlarr indexer IDs to search; empty searches all.
    prowlarr_indexer_ids: str = ""
    prowlarr_timeout_seconds: int = 15

    # --- CORS ---
    # Read as a plain string: pydantic-settings JSON-decodes list-typed env
    # vars, so CORS_ORIGINS=* (or a,b) would crash at startup. Accepts "*",
    # a comma-separated list, or a JSON list.
    cors_origins_raw: str = Field(
        default="*",
        validation_alias="CORS_ORIGINS",
        description="Allowed CORS origins",
    )

    @property
    def cors_origins(self) -> list[str]:
        raw = self.cors_origins_raw.strip()

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except ValueError:
                parsed = None

            if isinstance(parsed, list):
                return [str(origin).strip() for origin in parsed if str(origin).strip()]

        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        return origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
