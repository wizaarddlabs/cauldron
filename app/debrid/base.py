"""
Abstract interface every debrid provider client must implement.

Adding a new provider = subclass this and implement the four methods.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.models import CacheStatus, ResolveResponse


class DebridClient(ABC):
    """Common contract for all debrid service integrations."""

    provider_name: str

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def check_cache(self, info_hashes: list[str]) -> dict[str, CacheStatus]:
        """
        Given a list of torrent info hashes, return which ones are already
        cached on the debrid provider's servers (instant playback, no
        waiting for a real download).
        """
        raise NotImplementedError

    @abstractmethod
    async def add_magnet(self, magnet: str) -> str:
        """Add a magnet link to the user's debrid account. Returns a torrent/item ID."""
        raise NotImplementedError

    @abstractmethod
    async def list_files(self, torrent_id: str) -> list[dict]:
        """List playable files within an added torrent."""
        raise NotImplementedError

    @abstractmethod
    async def get_playback_link(
        self, torrent_id: str, file_index: Optional[int] = None
    ) -> ResolveResponse:
        """Resolve a direct, unrestricted streaming/download link for a file."""
        raise NotImplementedError
