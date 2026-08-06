import json
from pathlib import Path
from dataclasses import asdict

from app.ranking.preferences import RankingPreferences


PREF_FILE = Path("/data/ranking_preferences.json")


def load_preferences() -> RankingPreferences:
    """
    Load ranking preferences.
    Defaults if none exist.
    """

    defaults = RankingPreferences()

    if not PREF_FILE.exists():
        return defaults

    try:
        data = json.loads(
            PREF_FILE.read_text()
        )

        # Handle legacy data format where resolution/codec might be strings or incomplete lists
        if isinstance(data.get('resolution'), str) or not isinstance(data.get('resolution'), list):
            data['resolution'] = defaults.resolution
        elif len(data.get('resolution', [])) < len(defaults.resolution):
            # If the list is incomplete, use defaults
            data['resolution'] = defaults.resolution

        if isinstance(data.get('codec'), str) or not isinstance(data.get('codec'), list):
            data['codec'] = defaults.codec
        elif len(data.get('codec', [])) < len(defaults.codec):
            # If the list is incomplete, use defaults
            data['codec'] = defaults.codec

        # Merge loaded data with defaults to ensure all fields have values
        default_dict = asdict(defaults)
        default_dict.update(data)

        return RankingPreferences(
            **default_dict
        )

    except Exception:
        return defaults


def save_preferences(
    preferences: RankingPreferences,
):
    """
    Save ranking preferences.
    """

    PREF_FILE.parent.mkdir(parents=True, exist_ok=True)

    PREF_FILE.write_text(
        json.dumps(
            preferences.__dict__,
            indent=2,
        )
    )
