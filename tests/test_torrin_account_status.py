from app.api.stremio import (
    _mark_torrin_account_results_cached,
    _prioritize_torrin_account_results,
)
from app.filtering.matchers import matches_codec
from app.models import CacheStatus, TorrentResult


def test_completed_torrin_account_result_is_cached_for_user():
    torrent = TorrentResult(
        title="Movie.2025.1080p.mkv",
        info_hash="a" * 40,
        magnet="magnet:?xt=urn:btih:" + "a" * 40,
        source="torrin-account",
    )

    status_map = {torrent.info_hash: CacheStatus.NOT_CACHED}

    _mark_torrin_account_results_cached(status_map, [torrent])

    assert status_map[torrent.info_hash] == CacheStatus.CACHED


def test_torrin_account_results_are_prioritized_before_public_results():
    account = TorrentResult(
        title="Account Movie",
        info_hash="a" * 40,
        magnet="magnet:?xt=urn:btih:" + "a" * 40,
        source="torrin-account",
    )
    public = TorrentResult(
        title="Public Movie",
        info_hash="b" * 40,
        magnet="magnet:?xt=urn:btih:" + "b" * 40,
        source="public",
    )

    prioritized = _prioritize_torrin_account_results([public, account])

    assert prioritized[0] is account


def test_codec_filter_accepts_torrin_h265_filename():
    assert matches_codec(
        "Evil.Dead.Burn.2026.2160p.H.265.WEB-DL.mkv",
        ["hevc"],
    )