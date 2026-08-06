import re


def quality_score(title: str) -> int:

    t = title.lower()

    score = 0

    # Resolution priority
    if re.search(r"\b(2160p|4k|uhd)\b", t):
        score += 5000

    elif re.search(r"\b1440p\b", t):
        score += 4000

    elif re.search(r"\b1080p\b", t):
        score += 3000

    elif re.search(r"\b720p\b", t):
        score += 2000

    elif re.search(r"\b(576p|480p|360p)\b", t):
        score += 1000


    # Quality bonuses
    if "remux" in t:
        score += 500

    if "dolby vision" in t or re.search(r"\bdv\b", t):
        score += 400

    if "hdr" in t:
        score += 200

    if "atmos" in t:
        score += 100

    if "hevc" in t or "x265" in t:
        score += 100


    return score



def sort_torrents(torrents):

    return sorted(
        torrents,
        key=lambda x: quality_score(x.title),
        reverse=True
    )