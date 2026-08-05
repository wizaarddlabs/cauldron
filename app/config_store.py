import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime


DB = Path("/data/cauldron.db")


def init_db():

    DB.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS configs (
        id TEXT PRIMARY KEY,
        created TEXT,
        data TEXT
    )
    """)

    conn.commit()
    conn.close()



def save_config(data):

    init_db()

    config_id = str(uuid.uuid4())[:8]

    conn = sqlite3.connect(DB)

    conn.execute(
        """
        INSERT INTO configs
        VALUES (?, ?, ?)
        """,
        (
            config_id,
            datetime.utcnow().isoformat(),
            json.dumps(data)
        )
    )

    conn.commit()
    conn.close()

    return config_id



def load_config(config_id):

    init_db()

    conn = sqlite3.connect(DB)

    row = conn.execute(
        """
        SELECT data FROM configs WHERE id=?
        """,
        (config_id,)
    ).fetchone()

    conn.close()

    if not row:
        return None

    return json.loads(row[0])
