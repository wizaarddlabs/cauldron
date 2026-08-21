from dataclasses import dataclass, asdict, field
from pathlib import Path
import json


PREF_FILE = Path("/data/ranking_preferences.json")


@dataclass
class RankingPreferences:

    # Sorting
    sort_mode: str = "balanced"


    # Playback preferences
    resolution: list[str] = field(default_factory=lambda: ["2160p", "1440p", "1080p", "720p", "576p", "480p", "360p", "240p", "unknown"])

    language: list[str] = field(default_factory=list)

    required_languages: list[str] = field(default_factory=list)

    preferred_languages: list[str] = field(default_factory=list)

    excluded_languages: list[str] = field(default_factory=list)

    audio: str = "any"

    quality_profile: str = "balanced"

    codec: list[str] = field(default_factory=lambda: ["hevc", "h264", "av1", "remux"])



    # Quality boosts

    prefer_4k: bool = True

    prefer_hdr: bool = True

    prefer_dolby_vision: bool = True

    prefer_remux: bool = True

    prefer_hevc: bool = True

    prefer_atmos: bool = True

    allow_cam: bool = False

    allow_season_packs: bool = False

    min_seeders: int = 0

    seeder_weight: float = 1.0

    # Sorting
    sort_criteria: list[str] = field(default_factory=lambda: ["seeders", "resolution", "quality"])
    sort_order: str = "desc"

    # Additional fields from web form
    filters: list[str] = field(default_factory=list)
    custom_patterns: str = ""
    cached_only: bool = False
    dedupe_streams: bool = False
    max_per_resolution: int = 0
    max_size_gb: float = 0

    # Debrid API keys
    torrin_key: str = ""
    torbox_key: str = ""
    realdebrid_key: str = ""
    alldebrid_key: str = ""
    premiumize_key: str = ""
    offcloud_key: str = ""



def get_preferences():

    if not PREF_FILE.exists():

        prefs = RankingPreferences()

        save_preferences(
            asdict(prefs)
        )

        return prefs


    try:

        with open(PREF_FILE,"r") as f:

            data=json.load(f)


        return RankingPreferences(
            **data
        )


    except Exception:

        return RankingPreferences()



def save_preferences(data):

    PREF_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    if isinstance(
        data,
        RankingPreferences
    ):

        data=asdict(data)



    with open(
        PREF_FILE,
        "w"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )


    return data
