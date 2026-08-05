from app.models import TorrentResult
from app.ranking.preferences import RankingPreferences


def score_result(
    result: TorrentResult,
    prefs: RankingPreferences,
) -> float:

    title = result.title.lower()

    score = 0


    # Seeders
    score += (result.seeders or 0) * prefs.seeder_weight


    # Quality
    if prefs.prefer_4k:
        if "2160p" in title or "4k" in title:
            score += 100


    if prefs.prefer_hdr:
        if "hdr" in title:
            score += 50


    if prefs.prefer_dolby_vision:
        if "dv" in title or "dolby vision" in title:
            score += 75


    if prefs.prefer_remux:
        if "remux" in title:
            score += 100


    if prefs.prefer_hevc:
        if "x265" in title or "hevc" in title:
            score += 30


    # Penalize bad releases
    if not prefs.allow_cam:
        if (
            "cam"
            in title
            or "hdcam"
            in title
            or "ts"
            in title
        ):
            score -= 500


    return score


def rank_results(
    results: list[TorrentResult],
    prefs: RankingPreferences,
) -> list[TorrentResult]:

    return sorted(
        results,
        key=lambda r: score_result(r, prefs),
        reverse=True,
    )
