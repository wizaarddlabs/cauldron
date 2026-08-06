"""Filtering pipeline for torrent results.

This provides a small, extensible pipeline that applies multiple
filters (resolution, language, codec, seeders) to docker-compose restart appa list of
`TorrentResult` objects using the UI config dictionary.
"""
from typing import List

from app.filtering.resolution import matches_resolution
from app.filtering.matchers import matches_language, matches_codec
from app.models import TorrentResult


class FilterPipeline:
    def __init__(self, cfg: dict | None):
        self.cfg = cfg or {}

    def apply(self, torrents: List[TorrentResult]) -> List[TorrentResult]:
        """Return a filtered list of `torrents` according to `self.cfg`.

        Supported keys in `cfg`:
        - `resolution`: list of allowed resolution strings (e.g. ["2160p"])
        - `min_seeders`: integer lower bound for `torrent.seeders`
        - `language`: list of allowed language strings to look for in title
        - `codec`: list of codec keywords to match in title
        """

        res_allowed = self.cfg.get("resolution", []) or []

        try:
            min_seeders = int(self.cfg.get("min_seeders", 0) or 0)
        except Exception:
            min_seeders = 0

        languages = self.cfg.get("language") or []
        codecs = self.cfg.get("codec") or []

        out: List[TorrentResult] = []

        for t in torrents:
            # Resolution
            if not matches_resolution(t.title, res_allowed):
                continue

            # Seeders
            if (t.seeders or 0) < min_seeders:
                continue

            title_lower = t.title.lower()

            # Language (regex-backed matching)
            if not matches_language(t.title, languages):
                continue

            # Codec (regex-backed matching)
            if not matches_codec(t.title, codecs):
                continue

                # Max size filter (GB)
                try:
                    max_size_gb = float(self.cfg.get("max_size_gb", 0) or 0)
                except Exception:
                    max_size_gb = 0

                if max_size_gb > 0 and t.size_bytes:

                    if t.size_bytes > int(max_size_gb * 1024 * 1024 * 1024):
                        continue



            # Deduplicate streams if requested (keep first occurrence per info_hash)
            dedupe = bool(self.cfg.get("dedupe_streams"))

            if dedupe:

                seen = set()
                deduped = []

                for t in out:

                    if t.info_hash in seen:
                        continue

                    seen.add(t.info_hash)
                    deduped.append(t)

                out = deduped

            # Enforce max per resolution (0 => no limit)
            try:
                max_per = int(self.cfg.get("max_per_resolution", 0) or 0)
            except Exception:
                max_per = 0

            if max_per > 0:

                buckets = {}
                limited: List[TorrentResult] = []

                for t in out:

                    res = detect_resolution(t.title) or t.quality or "unknown"

                    cnt = buckets.get(res, 0)

                    if cnt >= max_per:
                        continue

                    buckets[res] = cnt + 1
                    limited.append(t)

                out = limited

            out.append(t)

        return out
