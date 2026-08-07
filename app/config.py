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

    # --- Debrid provider API bases (rarely need changing) ---
    realdebrid_api_base: str = "https://api.real-debrid.com/rest/1.0"
    alldebrid_api_base: str = "https://api.alldebrid.com/v4.1"
    premiumize_api_base: str = "https://www.premiumize.me/api"
    torbox_api_base: str = "https://api.torbox.app/v1/api"

    # --- Cache ---
    redis_url: Optional[str] = Field(default=None, description="e.g. redis://localhost:6379/0")
    cache_ttl_search: int = 60 * 60       # 1 hour for scrape results (increased for high-traffic)
    cache_ttl_availability: int = 60 * 15  # 15 min for debrid-cache checks
    redis_max_memory: str = "512mb"      # Redis max memory limit for production
    redis_eviction_policy: str = "allkeys-lru"  # Evict least recently used keys

    # --- Search behavior ---
    max_results_per_scraper: int = 200  # Soft limit for individual scrapers (can be exceeded)
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
