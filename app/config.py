"""
Application configuration.
All values are overridable via environment variables / .env file.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- General ---
    app_name: str = "Cauldron"
    log_level: str = "INFO"
    addon_id: str = "community.cauldron"
    addon_name: str = "Cauldron"
    addon_version: str = "0.1.0"
    addon_url: str = "http://localhost:8000"

    # --- Jackett (self-hosted torrent indexer aggregator) ---
    # Point this at your own Jackett instance. Jackett handles talking to
    # whichever indexers you personally configure there; this project never
    # hardcodes specific tracker scrapers.
    jackett_url: Optional[str] = Field(default=None, description="e.g. http://localhost:9117")
    jackett_api_key: Optional[str] = None
    jackett_indexers: str = "all"  # comma-separated Jackett indexer IDs, or "all"

    # --- Debrid provider API bases (rarely need changing) ---
    realdebrid_api_base: str = "https://api.real-debrid.com/rest/1.0"
    alldebrid_api_base: str = "https://api.alldebrid.com/v4"
    premiumize_api_base: str = "https://www.premiumize.me/api"
    torbox_api_base: str = "https://api.torbox.app/v1/api"

    # --- Cache ---
    redis_url: Optional[str] = Field(default=None, description="e.g. redis://localhost:6379/0")
    cache_ttl_search: int = 60 * 30       # 30 min for scrape results
    cache_ttl_availability: int = 60 * 10  # 10 min for debrid-cache checks

    # --- Search behavior ---
    max_results_per_scraper: int = 50
    scrape_timeout_seconds: int = 20

    # --- CORS ---
    cors_origins: list[str] = Field(default=["*"], description="Allowed CORS origins")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
