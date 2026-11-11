"""
Multiple debrid providers per addon.

A config may list several debrid accounts in priority order. Every search
checks all of their caches concurrently; each torrent is then streamed through
the first provider (by priority) that has it cached, or the first provider if
none do. With ``stream_mode == "all"`` one stream per provider is listed
instead.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.logging_utils import redact_value
from app.models import CacheStatus

logger = logging.getLogger(__name__)

# Display names, in the order the setup page offers them.
PROVIDER_LABELS: dict[str, str] = {
    "torrin": "Torrin",
    "torbox": "TorBox",
    "realdebrid": "Real-Debrid",
    "alldebrid": "AllDebrid",
    "premiumize": "Premiumize",
    "offcloud": "Offcloud",
}

STREAM_MODE_BEST = "best"
STREAM_MODE_ALL = "all"
STREAM_MODES = (STREAM_MODE_BEST, STREAM_MODE_ALL)

# A slow provider must not hold every stream response hostage.
CACHE_CHECK_TIMEOUT_SECONDS = 12


@dataclass
class DebridAccount:
    provider: str
    api_key: str
    client: Any = field(default=None, repr=False)

    @property
    def label(self) -> str:
        return PROVIDER_LABELS.get(self.provider, self.provider)


def accounts_from_config(cfg: dict) -> list[tuple[str, str]] | None:
    """
    Read the ``providers`` list from a config, in priority order.

    Returns ``None`` when the config has no such list (an older,
    single-provider config), so the caller can use the legacy fields.
    Invalid, duplicate or keyless entries are skipped.
    """

    entries = cfg.get("providers")

    if not isinstance(entries, list):
        return None

    accounts: list[tuple[str, str]] = []
    seen: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        provider = str(entry.get("provider") or "").strip().lower()
        api_key = str(entry.get("api_key") or "").strip()

        if provider in PROVIDER_LABELS and api_key and provider not in seen:
            accounts.append((provider, api_key))
            seen.add(provider)

    return accounts


async def check_all_caches(
    accounts: list[DebridAccount],
    info_hashes: list[str],
    timeout: float = CACHE_CHECK_TIMEOUT_SECONDS,
) -> dict[str, dict[str, CacheStatus]]:
    """
    Check every account's cache concurrently.

    Returns ``{provider: {info_hash: status}}``. A provider that fails or
    times out gets an empty map, so its streams show as "unknown".
    """

    async def check(account: DebridAccount) -> dict[str, CacheStatus]:
        try:
            return await asyncio.wait_for(
                account.client.check_cache(info_hashes),
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning(
                "%s cache check timed out after %ss", account.label, timeout
            )
        except Exception as exc:
            logger.warning(
                "%s cache check failed: %s",
                account.label,
                redact_value(exc, account.api_key),
            )
        return {}

    if not info_hashes or not accounts:
        return {account.provider: {} for account in accounts}

    results = await asyncio.gather(*(check(account) for account in accounts))

    return {
        account.provider: {
            str(info_hash).lower(): status
            for info_hash, status in (result or {}).items()
        }
        for account, result in zip(accounts, results, strict=True)
    }


def combine_cache_status(
    per_provider: dict[str, dict[str, CacheStatus]],
    info_hashes: list[str],
) -> dict[str, CacheStatus]:
    """
    One status per torrent across all providers, used for sorting and the
    cached-only filter: cached anywhere wins, then known-uncached, else unknown.
    """

    combined: dict[str, CacheStatus] = {}

    for info_hash in info_hashes:
        statuses = [
            status_map.get(info_hash, CacheStatus.UNKNOWN)
            for status_map in per_provider.values()
        ]

        if CacheStatus.CACHED in statuses:
            combined[info_hash] = CacheStatus.CACHED
        elif CacheStatus.NOT_CACHED in statuses:
            combined[info_hash] = CacheStatus.NOT_CACHED
        else:
            combined[info_hash] = CacheStatus.UNKNOWN

    return combined


def accounts_for_torrent(
    info_hash: str,
    accounts: list[DebridAccount],
    per_provider: dict[str, dict[str, CacheStatus]],
    stream_mode: str = STREAM_MODE_BEST,
) -> list[DebridAccount]:
    """
    The account(s) to offer a torrent through, in display order.

    ``best``: the highest-priority account that has it cached, else the
    highest-priority account. ``all``: every account, in priority order.
    """

    if not accounts:
        return []

    if stream_mode == STREAM_MODE_ALL:
        return list(accounts)

    for account in accounts:
        status = per_provider.get(account.provider, {}).get(info_hash)
        if status == CacheStatus.CACHED:
            return [account]

    return [accounts[0]]
