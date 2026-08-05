"""
Core data models shared across scrapers, debrid clients, and API layers.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TorrentResult(BaseModel):
    """A single result returned by a scraper, before debrid resolution."""

    title: str
    info_hash: str = Field(..., description="40-char hex BitTorrent info hash")
    magnet: str
    size_bytes: Optional[int] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None
    source: str = Field(..., description="Name of the scraper/indexer that found this")
    indexer: Optional[str] = None
    quality: Optional[str] = Field(default=None, description="e.g. 2160p, 1080p, 720p, CAM")
    codec: Optional[str] = None
    published_at: Optional[str] = None


class DebridProvider(str, Enum):
    REAL_DEBRID = "realdebrid"
    ALLDEBRID = "alldebrid"
    PREMIUMIZE = "premiumize"
    TORBOX = "torbox"


class CacheStatus(str, Enum):
    CACHED = "cached"
    NOT_CACHED = "not_cached"
    UNKNOWN = "unknown"


class StreamCandidate(BaseModel):
    """A TorrentResult enriched with debrid cache/availability info."""

    torrent: TorrentResult
    provider: DebridProvider
    cache_status: CacheStatus = CacheStatus.UNKNOWN
    playback_url: Optional[str] = None
    file_name: Optional[str] = None


class ResolveRequest(BaseModel):
    provider: DebridProvider
    api_key: str
    magnet: str
    file_index: Optional[int] = Field(
        default=None, description="Which file to pick if the torrent has multiple files"
    )


class ResolveResponse(BaseModel):
    playback_url: str
    file_name: Optional[str] = None
    provider: DebridProvider
