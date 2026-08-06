from app.models import TorrentResult
from app.ranking.preferences import RankingPreferences


def score_result(
    result: TorrentResult,
    prefs: RankingPreferences,
) -> float:

    title = result.title.lower()

    score = 0


    # =====================
    # Resolution priority
    # =====================

    if "2160p" in title or "4k" in title:
        score += 400

    elif "1440p" in title:
        score += 300

    elif "1080p" in title:
        score += 200

    elif "720p" in title:
        score += 100


    # =====================
    # Premium formats
    # =====================

    if "remux" in title:
        score += 250


    if "dolby vision" in title:
        score += 150

    elif " dv " in title or title.startswith("dv ") or title.endswith(" dv"):
        score += 150


    if "hdr" in title:
        score += 100


    # =====================
    # Codec
    # =====================

    if "x265" in title or "hevc" in title:
        score += 75


    if "av1" in title:
        score += 50


    if "x264" in title or "h264" in title:
        score += 25



    # =====================
    # Seeders
    # =====================

    score += (
        result.seeders or 0
    ) * prefs.seeder_weight



    # =====================
    # Bad releases
    # =====================

    if not prefs.allow_cam:

        bad = [
            "cam",
            "hdcam",
            "ts",
            "telesync"
        ]

        for word in bad:
            if word in title:
                score -= 1000



    return score



def rank_results(
    results:list[TorrentResult],
    prefs:RankingPreferences,
):

    return sorted(
        results,
        key=lambda r: score_result(r,prefs),
        reverse=True,
    )