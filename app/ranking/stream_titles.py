def build_stream_name(title: str):

    t = title.lower()

    badges=[]


    if "2160p" in t or "4k" in t:
        badges.append("4K")

    elif "1080p" in t:
        badges.append("1080p")


    if "remux" in t:
        badges.append("REMUX")


    if "dolby vision" in t or " dv " in f" {t} ":
        badges.append("DV")


    if "hdr" in t:
        badges.append("HDR")


    if "x265" in t or "hevc" in t:
        badges.append("HEVC")


    if badges:
        return (
            "🧙 Cauldron ⚡ "
            + " ".join(badges)
        )


    return "🧙 Cauldron"