"""Filtering pipeline for torrent results."""

from typing import List

from app.filtering.resolution import (
    matches_resolution,
    detect_resolution,
)

from app.filtering.matchers import (
    matches_language,
    matches_codec,
)

from app.models import TorrentResult


class FilterPipeline:

    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}


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

            # Resolution filter
            if not matches_resolution(
                t.title,
                res_allowed
            ):
                continue


            # Seeder filter
            if (
                t.seeders or 0
            ) < min_seeders:
                continue


            # Language filter
            if not matches_language(
                t.title,
                languages
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

                if t.info_hash in seen:
                    continue

                seen.add(
                    t.info_hash
                )

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

                res = (
                    detect_resolution(
                        t.title
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