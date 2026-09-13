"""Read-only access to the aviation database.

The database is built by etl/build_db.py. In Azure it lives on a mounted
Azure Files share written by the scheduled ETL job; locally it sits in data/.
"""

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("DB_DIR", ROOT / "data")) / "airports.db"

_con: sqlite3.Connection | None = None
_mtime: float | None = None


def connection() -> sqlite3.Connection:
    """Shared read-only connection. Rows come back as sqlite3.Row.

    immutable=1 tells SQLite to skip locking entirely. That is required on
    Azure Files, which does not support the byte-range locks SQLite normally
    takes, and is safe here because the ETL job replaces the file rather than
    writing into it.

    Because immutable=1 means the open handle never sees later writes, the
    file's mtime is checked on every call: when the monthly ETL job swaps in a
    new database the connection is reopened, so no restart is needed.
    """
    global _con, _mtime
    if not DB_PATH.exists():
        raise RuntimeError(f"{DB_PATH} not found. Run: python etl/build_db.py")
    current = DB_PATH.stat().st_mtime
    if _con is None or current != _mtime:
        if _con is not None:
            _con.close()
        _con = sqlite3.connect(
            f"file:{DB_PATH}?mode=ro&immutable=1", uri=True, check_same_thread=False
        )
        _con.row_factory = sqlite3.Row
        _mtime = current
    return _con


def query(sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in connection().execute(sql, params).fetchall()]


def coverage() -> dict:
    """What the database currently contains, for scoping and caveats."""
    rows = query("SELECT source, coverage, fetched FROM source_meta")
    span = query(
        "SELECT MIN(year*100+month) lo, MAX(year*100+month) hi,"
        " COUNT(DISTINCT year*100+month) months FROM airport_month"
    )[0]
    return {
        "sources": {r["source"]: f"{r['coverage']} (fetched {r['fetched']})" for r in rows},
        "flight_months": span["months"],
        "flight_range": f"{span['lo']}-{span['hi']}" if span["lo"] else None,
    }
