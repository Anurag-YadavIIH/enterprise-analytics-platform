"""Load the processed Parquet data into the PostgreSQL star schema.

The container's initdb scripts (sql/ddl) create empty tables; this script
fills them from ``data/processed`` using the same shaping logic as the DuckDB
builder, so the two warehouses stay identical. Run after ``eap ingest run``::

    python scripts/load_postgres.py
    python scripts/load_postgres.py --truncate   # reload from scratch

Requires a reachable Postgres (docker compose up postgres).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import pandas as pd
from sqlalchemy import create_engine, text

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from eap.config import get_settings  # noqa: E402
from eap.utils.logging import configure_logging, get_logger  # noqa: E402

configure_logging()
log = get_logger("scripts.load_postgres")

# Load order respects FK dependencies in sql/ddl/01_schema.sql.
LOAD_ORDER = (
    "dim_customers",
    "dim_sellers",
    "dim_products",
    "dim_geography",
    "dim_dates",
    "fact_orders",
    "fact_order_items",
    "fact_payments",
    "fact_reviews",
)


def _frames_from_duckdb() -> dict[str, pd.DataFrame]:
    """Build the star-schema frames using the DuckDB builder's output.

    Reuses the already-built DuckDB warehouse if present; otherwise builds it
    on the fly. This guarantees Postgres receives exactly the same shaped
    tables as DuckDB.
    """
    settings = get_settings()
    db = settings.duckdb_file
    if not db.exists():
        from eap.warehouse import build_warehouse

        db = build_warehouse()

    con = duckdb.connect(str(db), read_only=True)
    try:
        return {t: con.execute(f"SELECT * FROM {t}").fetchdf() for t in LOAD_ORDER}
    finally:
        con.close()


def load(truncate: bool = False, chunksize: int = 10_000) -> None:
    settings = get_settings()
    engine = create_engine(settings.warehouse_url)
    frames = _frames_from_duckdb()

    with engine.begin() as conn:
        conn.execute(text("SET search_path TO olist, public"))
        if truncate:
            # Reverse order so FK children truncate first.
            for table in reversed(LOAD_ORDER):
                conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
            log.info("postgres.truncated", tables=len(LOAD_ORDER))

    for table in LOAD_ORDER:
        df = frames[table]
        df.to_sql(
            table,
            engine,
            schema="olist",
            if_exists="append",
            index=False,
            chunksize=chunksize,
            method="multi",
        )
        log.info("postgres.loaded", table=table, rows=len(df))

    log.info("postgres.load_complete", tables=len(LOAD_ORDER))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truncate", action="store_true", help="Truncate tables before load")
    parser.add_argument("--chunksize", type=int, default=10_000)
    args = parser.parse_args()
    load(truncate=args.truncate, chunksize=args.chunksize)
