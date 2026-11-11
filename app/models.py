"""
Core data models shared across scrapers, debrid clients, and API layers.
"""
from enum import Enum

from pydantic import BaseModel, Field


class TorrentResult(BaseModel):
    """A single result returned by a scraper, before debrid resolution."""

    title: str
    info_hash: str = Field(..., description="40-char hex BitTorrent info hash")
    magnet: str
    size_bytes: int | None = None
    seeders: int | None = None
    leechers: int | None = None
    source: str = Field(..., description="Name of the scraper/indexer that found this")
    indexer: str | None = None
    quality: str | None = Field(default=None, description="e.g. 2160p, 1080p, 720p, CAM")
    codec: str | None = None
    published_at: str | None = None


class DebridProvider(str, Enum):
    REAL_DEBRID = "realdebrid"
    ALLDEBRID = "alldebrid"
    PREMIUMIZE = "premiumize"
    TORBOX = "torbox"
    TORRIN = "torrin"
    OFFCLOUD = "offcloud"


class CacheStatus(str, Enum):
    CACHED = "cached"
    NOT_CACHED = "not_cached"
    UNKNOWN = "unknown"


class StreamCandidate(BaseModel):
    """A TorrentResult enriched with debrid cache/availability info."""

    torrent: TorrentResult
    provider: DebridProvider
    cache_status: CacheStatus = CacheStatus.UNKNOWN
    playback_url: str | None = None
    file_name: str | None = None


class AvailabilityRequest(BaseModel):
    q: str
    provider: DebridProvider
    api_key: str
    imdb_id: str | None = None
    season: str | None = None
    episode: str | None = None
    media_type: str | None = None


class ResolveRequest(BaseModel):
    provider: DebridProvider
    api_key: str
    magnet: str
    file_index: int | None = Field(
        default=None, description="Which file to pick if the torrent has multiple files"
    )


class ResolveResponse(BaseModel):
    playback_url: str
    file_name: str | None = None
    provider: DebridProvider
