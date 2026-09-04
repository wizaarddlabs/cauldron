"""Filtering pipeline for torrent results."""

from typing import List

from app.filtering.resolution import (
    matches_resolution,
    detect_resolution,
)

from app.filtering.matchers import (
    matches_language,
    matches_required_languages,
    matches_excluded_languages,
    matches_codec,
)

from app.models import TorrentResult


class FilterPipeline:

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    @staticmethod
    def _resolution_text(torrent: TorrentResult) -> str:
        """
        Build the text used for resolution detection.

        Some scrapers, especially Zilean, provide resolution
        separately from the torrent title. Include both so that
        an explicit resolution such as 2160p/4K is not lost.
        """

        title = str(
            getattr(torrent, "title", "")
            or ""
        )

        quality = str(
            getattr(torrent, "quality", "")
            or ""
        )

        if quality:
            return f"{title} {quality}"

        return title

    def apply(
        self,
        torrents: List[TorrentResult]
    ) -> List[TorrentResult]:

        res_allowed = self.cfg.get(
            "resolution",
            []
        ) or []

        languages = self.cfg.get(
            "language",
            []
        ) or []

        required_languages = self.cfg.get(
            "required_languages",
            []
        ) or []

        preferred_languages = self.cfg.get(
            "preferred_languages",
            []
        ) or []

        excluded_languages = self.cfg.get(
            "excluded_languages",
            []
        ) or []

        codecs = self.cfg.get(
            "codec",
            []
        ) or []

        try:
            min_seeders = int(
                self.cfg.get(
                    "min_seeders",
                    0
                )
            )
        except Exception:
            min_seeders = 0

        try:
            max_size_gb = float(
                self.cfg.get(
                    "max_size_gb",
                    0
                )
            )
        except Exception:
            max_size_gb = 0

        filtered = []

        for t in torrents:

            # Resolution filter.
            #
            # Use both the title and the explicit quality/resolution
            # field supplied by the scraper.
            resolution_text = self._resolution_text(t)

            if not matches_resolution(
                resolution_text,
                res_allowed
            ):
                continue

            # Seeder filter
            if (
                t.seeders or 0
            ) < min_seeders:
                continue

            # Language filter (general)
            # Skip if required or excluded languages are set, as those are more specific
            if not required_languages and not excluded_languages:
                if not matches_language(
                    t.title,
                    languages
                ):
                    continue

            # Required languages filter (must contain at least one)
            if not matches_required_languages(
                t.title,
                required_languages
            ):
                continue

            # Excluded languages filter (must not contain any)
            if not matches_excluded_languages(
                t.title,
                excluded_languages
            ):
                continue

            # Codec filter
            if not matches_codec(
                t.title,
                codecs
            ):
                continue

            # Size filter
            if (
                max_size_gb > 0
                and t.size_bytes
                and t.size_bytes >
                int(max_size_gb * 1024 * 1024 * 1024)
            ):
                continue

            filtered.append(t)

        # Deduplicate
        if self.cfg.get(
            "dedupe_streams"
        ):

            seen = set()
            deduped = []

            for t in filtered:
                # Handle missing info_hash like the aggregator does
                info_hash = str(
                    getattr(t, "info_hash", "") or ""
                ).lower()

                if not info_hash:
                    # Results without an info hash cannot be safely deduplicated
                    # Create a unique key from title and magnet
                    unique_key = (
                        f"nohash:"
                        f"{getattr(t, 'title', '')}:"
                        f"{getattr(t, 'magnet', '')}"
                    )
                else:
                    unique_key = info_hash

                if unique_key in seen:
                    continue

                seen.add(unique_key)
                deduped.append(t)

            filtered = deduped

        # Limit results per resolution
        try:
            max_per = int(
                self.cfg.get(
                    "max_per_resolution",
                    0
                )
            )
        except Exception:
            max_per = 0

        if max_per > 0:

            buckets = {}
            limited = []

            for t in filtered:

                resolution_text = (
                    self._resolution_text(t)
                )

                res = (
                    detect_resolution(
                        resolution_text
                    )
                    or "unknown"
                )

                count = buckets.get(
                    res,
                    0
                )

                if count >= max_per:
                    continue

                buckets[res] = count + 1

                limited.append(t)

            filtered = limited

        return filtered