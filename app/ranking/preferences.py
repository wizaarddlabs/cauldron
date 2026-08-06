from dataclasses import dataclass, asdict, field
from pathlib import Path
import json


PREF_FILE = Path("/data/ranking_preferences.json")


@dataclass
class RankingPreferences:

    # Sorting
    sort_mode: str = "balanced"


    # Playback preferences
    resolution: list[str] = field(default_factory=list)

    language: list[str] = field(default_factory=list)

    required_languages: list[str] = field(default_factory=list)

    preferred_languages: list[str] = field(default_factory=list)

    excluded_languages: list[str] = field(default_factory=list)

    multi_language: bool = False

    audio: str = "any"

    quality_profile: str = "balanced"

    codec: list[str] = field(default_factory=list)



    # Quality boosts

    prefer_4k: bool = True

    prefer_hdr: bool = True

    prefer_dolby_vision: bool = True

    prefer_remux: bool = True

    prefer_hevc: bool = True



    allow_cam: bool = False


    min_seeders: int = 0


    seeder_weight: float = 1.0

    # Additional fields from web form
    filters: list[str] = field(default_factory=list)
    custom_patterns: str = ""
    cached_only: bool = False
    dedupe_streams: bool = False
    scrape_debrid: bool = False
    max_per_resolution: int = 0
    max_size_gb: float = 0



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
