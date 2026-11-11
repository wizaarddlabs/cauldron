import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DB = Path("/data/cauldron.db")
_ENCRYPTED_PREFIX = "fernet:"


def _get_fernet() -> Fernet:
    key_path = DB.with_name("cauldron.key")

    try:
        key = key_path.read_bytes()
    except FileNotFoundError:
        generated_key = Fernet.generate_key()
        try:
            file_descriptor = os.open(
                key_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            key = key_path.read_bytes()
        else:
            with os.fdopen(file_descriptor, "wb") as key_file:
                key_file.write(generated_key)
            key = generated_key

    return Fernet(key)


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

    config_id = uuid.uuid4().hex

    with sqlite3.connect(DB) as conn:
        conn.execute(
            """
            INSERT INTO configs
            VALUES (?, ?, ?)
            """,
            (
                config_id,
                datetime.now(UTC).isoformat(),
                _ENCRYPTED_PREFIX
                + _get_fernet().encrypt(
                    json.dumps(data).encode("utf-8")
                ).decode("ascii")
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

    serialized = row[0]
    if not serialized.startswith(_ENCRYPTED_PREFIX):
        return json.loads(serialized)

    try:
        payload = _get_fernet().decrypt(
            serialized[len(_ENCRYPTED_PREFIX):].encode("ascii")
        )
    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt configuration; verify the persisted Cauldron key"
        ) from exc

    return json.loads(payload)
