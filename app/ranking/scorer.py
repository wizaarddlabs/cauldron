from app.models import TorrentResult
from app.ranking.preferences import RankingPreferences
from app.filtering.matchers import LANGUAGE_PATTERNS, _match_patterns
import re


def score_result(
    result: TorrentResult,
    prefs: RankingPreferences,
) -> float:

    title = result.title.lower()

    score = 0


    # =====================
    # Resolution priority (enhanced)
    # =====================

    if "2160p" in title or "4k" in title:
        score += 500

    elif "1440p" in title:
        score += 400

    elif "1080p" in title:
        score += 300

    elif "720p" in title:
        score += 200

    elif "576p" in title or "480p" in title:
        score += 100


    # =====================
    # Premium formats (enhanced)
    # =====================

    if "remux" in title:
        score += 300


    # Dolby Vision variants
    if "dolby vision" in title or "dv " in title or title.startswith("dv ") or title.endswith(" dv"):
        score += 200
        if "dvhe" in title or "dovi" in title:
            score += 50  # Dolby Vision HDR10+
            if "dv" in title and "p5" in title:
                score += 30  # Profile 5
            if "dv" in title and "p7" in title:
                score += 40  # Profile 7


    # HDR variants
    if "hdr10+" in title:
        score += 150
    elif "hdr10" in title:
        score += 120
    elif "hdr" in title:
        score += 80


    # Audio formats
    if "atmos" in title or "dolby atmos" in title:
        score += 100
        if "truehd" in title:
            score += 50  # Atmos TrueHD
    elif "dts-hd ma" in title:
        score += 80
    elif "dts-hd hra" in title:
        score += 70
    elif "dts" in title:
        score += 40
    elif "aac" in title:
        score += 20


    # Codec (enhanced)
    if "av1" in title:
        score += 100
    elif "x265" in title or "hevc" in title:
        score += 80
    elif "x264" in title or "h264" in title:
        score += 30


    # Channel count bonus
    if "7.1" in title or "8ch" in title:
        score += 40
    elif "5.1" in title or "6ch" in title:
        score += 20


    # =====================
    # Release group quality (basic)
    # =====================

    # Known high-quality release groups
    quality_groups = [
        "ctrlhd", "ctrl", "fgt", "node", "mteam", "sparks", "rzero", "wolf",
        "frds", "kog", "ntb", "ntg", "nzb", "yts", "yify", "rarbg",
        "frame", "sigma", "jyk", "dhd", "ethd", "evo", "blu", "gimini",
        "qts", "splinter", "demonoid", "cas", "club", "web", "bd"
    ]

    for group in quality_groups:
        if group in title:
            score += 50
            break


    # =====================
    # Content quality indicators
    # =====================

    if "web-dl" in title or "webrip" in title:
        score += 60
    elif "bluray" in title or "bdrip" in title:
        score += 80
    elif "brrip" in title:
        score += 40


    # =====================
    # Seeders (weighted)
    # =====================

    score += (
        result.seeders or 0
    ) * prefs.seeder_weight


    # =====================
    # Preferred languages bonus
    # =====================

    if prefs.preferred_languages:
        title_lower = result.title.lower()
        for lang in prefs.preferred_languages:
            patterns = LANGUAGE_PATTERNS.get(lang.lower())
            if patterns and _match_patterns(title_lower, patterns):
                score += 100  # Bonus for preferred language
                break  # Only bonus once even if multiple preferred languages match


    # =====================
    # Bad releases (enhanced)
    # =====================

    if not prefs.allow_cam:

        bad = [
            "cam",
            "hdcam",
            "ts",
            "telesync",
            "camrip",
            "scr",
            "dvdscr",
            "pdvd",
            "r5",
            "tc"
        ]

        for word in bad:
            if word in title:
                score -= 2000


    # =====================
    # Age factor (prefer newer releases)
    # =====================

    # Slight penalty for very old releases (basic implementation)
    # Could be enhanced with actual release date detection


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
