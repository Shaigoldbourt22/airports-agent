"""Per-user chat sessions stored in SQLite.

Lives on the mounted Azure Files share so history survives restarts.
Separate from the read-only aviation database in db.py.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

MAX_SESSIONS_PER_USER = 50
MAX_MESSAGES_PER_SESSION = 50

ROOT = Path(__file__).resolve().parent.parent
# Sessions sit beside the aviation database by default. SESSIONS_DIR moves them
# elsewhere, which a second deployment sharing the same volume needs: the
# connection below takes an exclusive lock for the life of the process, so two
# apps cannot write the same file, and test traffic should not land in real
# users' history either.
SESSIONS_DIR = os.environ.get("SESSIONS_DIR") or os.environ.get("DB_DIR")
DB_PATH = Path(SESSIONS_DIR or ROOT / "data") / "sessions.db"

_con: sqlite3.Connection | None = None
_lock = Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS session (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    updated TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS session_user ON session(user_id, updated DESC);

CREATE TABLE IF NOT EXISTS message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    file_names TEXT NOT NULL DEFAULT '[]',
    created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS message_session ON message(session_id, id);
"""


def _connect() -> sqlite3.Connection:
    global _con
    if _con is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        con.row_factory = sqlite3.Row
        # WAL needs shared memory, which SMB shares like Azure Files do not provide.
        con.execute("PRAGMA journal_mode=DELETE")
        # Azure Files does not support the byte-range locks SQLite normally takes
        # for every transaction, which surfaces as "database is locked". Taking a
        # single lock for the life of the process avoids them. Safe because the
        # app is pinned to one replica and _lock serialises writes in-process.
        con.execute("PRAGMA locking_mode=EXCLUSIVE")
        con.execute("PRAGMA busy_timeout=30000")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(SCHEMA)
        con.commit()
        _con = con
    return _con


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def list_sessions(user_id: str) -> list[dict]:
    with _lock:
        rows = _connect().execute(
            "SELECT id, title, updated FROM session"
            " WHERE user_id = ? ORDER BY updated DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_messages(user_id: str, session_id: str) -> list[dict]:
    """Messages for a session, oldest first. Empty if the session is not the user's.

    Only attachment names are kept, so replayed history has no file contents.
    """
    with _lock:
        rows = _connect().execute(
            "SELECT m.role, m.content, m.file_names FROM message m"
            " JOIN session s ON s.id = m.session_id"
            " WHERE m.session_id = ? AND s.user_id = ? ORDER BY m.id",
            (session_id, user_id),
        ).fetchall()
    return [
        {
            "role": row["role"],
            "content": row["content"],
            "file_names": json.loads(row["file_names"]),
        }
        for row in rows
    ]


def create_session(user_id: str, title: str) -> str:
    session_id = str(uuid.uuid4())
    with _lock:
        con = _connect()
        con.execute(
            "INSERT INTO session (id, user_id, title, updated) VALUES (?, ?, ?, ?)",
            (session_id, user_id, title[:80] or "New chat", _now()),
        )
        con.execute(
            "DELETE FROM session WHERE user_id = ? AND id NOT IN ("
            "  SELECT id FROM session WHERE user_id = ?"
            "  ORDER BY updated DESC LIMIT ?)",
            (user_id, user_id, MAX_SESSIONS_PER_USER),
        )
        con.commit()
    return session_id


def add_messages(user_id: str, session_id: str, messages: list[dict]) -> None:
    """Append messages, then trim the session to the most recent ones."""
    with _lock:
        con = _connect()
        owned = con.execute(
            "SELECT 1 FROM session WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not owned:
            return
        con.executemany(
            "INSERT INTO message (session_id, role, content, file_names, created)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (
                    session_id,
                    m["role"],
                    m["content"],
                    json.dumps(m.get("file_names") or []),
                    _now(),
                )
                for m in messages
            ],
        )
        con.execute(
            "DELETE FROM message WHERE session_id = ? AND id NOT IN ("
            "  SELECT id FROM message WHERE session_id = ?"
            "  ORDER BY id DESC LIMIT ?)",
            (session_id, session_id, MAX_MESSAGES_PER_SESSION),
        )
        con.execute(
            "UPDATE session SET updated = ? WHERE id = ?", (_now(), session_id)
        )
        con.commit()


def delete_session(user_id: str, session_id: str) -> None:
    with _lock:
        con = _connect()
        con.execute(
            "DELETE FROM session WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        con.commit()
