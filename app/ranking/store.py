import json
from pathlib import Path

from app.ranking.preferences import RankingPreferences


PREF_FILE = Path("/data/ranking_preferences.json")


def load_preferences() -> RankingPreferences:
    """
    Load ranking preferences.
    Defaults if none exist.
    """

    if not PREF_FILE.exists():
        return RankingPreferences()

    try:
        data = json.loads(
            PREF_FILE.read_text()
        )

        return RankingPreferences(
            **data
        )

    except Exception:
        return RankingPreferences()


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
