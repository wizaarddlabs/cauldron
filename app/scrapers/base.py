"""
Abstract interface every scraper/indexer source must implement.

Adding a new source = subclass this and implement `search`. The rest of the
app (caching, debrid resolution, Stremio formatting) works with any scraper
that returns a list[TorrentResult].
"""
from abc import ABC, abstractmethod

from app.models import TorrentResult


class Scraper(ABC):
    name: str

    @abstractmethod
    async def search(self, query: str, *, imdb_id: str | None = None) -> list[TorrentResult]:
        """
        Search this source for torrents matching a free-text query
        (and/or an IMDb id, when the source supports lookups by it).
        Must return quickly-parseable results with a valid info_hash.
        """
        raise NotImplementedError
