"""Database access for the API.

The API reads the DuckDB star-schema warehouse in **read-only** mode and
returns rows as dictionaries. A thin ``query`` helper centralises connection
handling and parameter binding so routers stay declarative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from eap.config import get_settings
from eap.utils.logging import get_logger

log = get_logger("api.db")


def _warehouse_path() -> Path:
    return get_settings().duckdb_file


def warehouse_exists() -> bool:
    return _warehouse_path().exists()


def query(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return a list of row dicts."""
    path = _warehouse_path()
    if not path.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {path}. Run `eap warehouse build` first."
        )
    con = duckdb.connect(str(path), read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    finally:
        con.close()


def query_one(sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None
