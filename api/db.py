"""Read-only DuckDB connection helper for the API layer."""
from __future__ import annotations
import os
from pathlib import Path
import duckdb

DB_PATH = Path(os.environ.get(
    "PYXIDA_DB",
    Path(__file__).resolve().parent.parent / "data" / "pyxida.duckdb"))

# DuckDB connections are not thread-safe to share; open per request via cursor.
_con = duckdb.connect(str(DB_PATH), read_only=True)


def q(sql: str, params: list | None = None) -> list[dict]:
    cur = _con.cursor()
    cur.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    cur.close()
    return [dict(zip(cols, r)) for r in rows]


def q1(sql: str, params: list | None = None) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None
