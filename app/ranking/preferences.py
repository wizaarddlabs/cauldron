from dataclasses import dataclass, asdict
from pathlib import Path
import json


PREF_FILE = Path("/data/ranking_preferences.json")


@dataclass
class RankingPreferences:

    # Sorting
    sort_mode: str = "balanced"


    # Playback preferences
    resolution: str = "any"

    language: str = "english"

    audio: str = "any"

    quality_profile: str = "balanced"

    codec: str = "any"



    # Quality boosts

    prefer_4k: bool = True

    prefer_hdr: bool = True

    prefer_dolby_vision: bool = True

    prefer_remux: bool = True

    prefer_hevc: bool = True



    allow_cam: bool = False


    min_seeders: int = 0


    seeder_weight: float = 1.0



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
