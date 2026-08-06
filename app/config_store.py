import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone


DB = Path("/data/cauldron.db")


def init_db():

    DB.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            id TEXT PRIMARY KEY,
            created TEXT,
            data TEXT
        )
        """)

        conn.commit()



def save_config(data):

    init_db()

    config_id = str(uuid.uuid4())[:8]

    with sqlite3.connect(DB) as conn:
        conn.execute(
            """
            INSERT INTO configs
            VALUES (?, ?, ?)
            """,
            (
                config_id,
                datetime.now(timezone.utc).isoformat(),
                json.dumps(data)
            )
        )

        conn.commit()

    return config_id



def load_config(config_id):

    init_db()

    with sqlite3.connect(DB) as conn:
        row = conn.execute(
            """
            SELECT data FROM configs WHERE id=?
            """,
            (config_id,)
        ).fetchone()

    if not row:
        return None

    return json.loads(row[0])
