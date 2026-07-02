"""Build the analytical star schema in DuckDB from cleaned Parquet.

This gives the platform a self-contained OLAP warehouse (``olist.duckdb``)
that the API, Streamlit app and ad-hoc SQL can all query without a running
Postgres. dbt builds richer marts on top of the same tables; this builder is
the deterministic, dependency-light baseline used by tests and the API.

Star schema produced
---------------------
Dimensions : dim_customers, dim_products, dim_sellers, dim_geography, dim_dates
Facts      : fact_orders, fact_order_items, fact_payments, fact_reviews
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from eap.config import Settings, get_settings
from eap.utils.io import timer
from eap.utils.logging import get_logger

log = get_logger(__name__)

_STAGING_TABLES = (
    "customers",
    "geolocation",
    "order_items",
    "order_payments",
    "order_reviews",
    "orders",
    "products",
    "sellers",
    "product_category_translation",
)


def _register_staging(con: duckdb.DuckDBPyConnection, processed_dir: Path) -> None:
    """Create ``stg_*`` tables from the processed Parquet files."""
    for name in _STAGING_TABLES:
        path = processed_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"Processed file missing: {path}. Run ingestion first."
            )
        con.execute(
            f"CREATE OR REPLACE TABLE stg_{name} AS "
            f"SELECT * FROM read_parquet('{path.as_posix()}')"
        )
    log.info("warehouse.staging_ready", tables=len(_STAGING_TABLES))


_DDL = """
-- ---------------- Dimensions ----------------
CREATE OR REPLACE TABLE dim_customers AS
SELECT
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
FROM stg_customers;

CREATE OR REPLACE TABLE dim_sellers AS
SELECT
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
FROM stg_sellers;

CREATE OR REPLACE TABLE dim_products AS
SELECT
    p.product_id,
    p.product_category_name,
    COALESCE(t.product_category_name_english, p.product_category_name) AS product_category_english,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.product_photos_qty
FROM stg_products p
LEFT JOIN stg_product_category_translation t
       ON p.product_category_name = t.product_category_name;

CREATE OR REPLACE TABLE dim_geography AS
SELECT
    geolocation_zip_code_prefix AS zip_code_prefix,
    AVG(geolocation_lat)        AS latitude,
    AVG(geolocation_lng)        AS longitude,
    ANY_VALUE(geolocation_city) AS city,
    ANY_VALUE(geolocation_state) AS state
FROM stg_geolocation
GROUP BY geolocation_zip_code_prefix;

-- Date dimension derived from the full range of order purchase timestamps.
CREATE OR REPLACE TABLE dim_dates AS
WITH bounds AS (
    SELECT
        CAST(MIN(order_purchase_timestamp) AS DATE) AS d_min,
        CAST(MAX(order_purchase_timestamp) AS DATE) AS d_max
    FROM stg_orders
),
series AS (
    SELECT UNNEST(range(d_min, d_max + INTERVAL 1 DAY, INTERVAL 1 DAY)) AS d
    FROM bounds
)
SELECT
    CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key,
    CAST(d AS DATE)                        AS date,
    EXTRACT(year   FROM d)                 AS year,
    EXTRACT(quarter FROM d)                AS quarter,
    EXTRACT(month  FROM d)                 AS month,
    strftime(d, '%B')                      AS month_name,
    EXTRACT(day    FROM d)                 AS day,
    EXTRACT(dayofweek FROM d)              AS day_of_week,
    strftime(d, '%A')                      AS day_name,
    EXTRACT(week   FROM d)                 AS week_of_year,
    CASE WHEN EXTRACT(dayofweek FROM d) IN (0, 6) THEN TRUE ELSE FALSE END AS is_weekend
FROM series;

-- ---------------- Facts ----------------
CREATE OR REPLACE TABLE fact_orders AS
SELECT
    o.order_id,
    o.customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    CAST(strftime(o.order_purchase_timestamp, '%Y%m%d') AS INTEGER) AS purchase_date_key,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    DATE_DIFF('day', o.order_purchase_timestamp, o.order_delivered_customer_date) AS delivery_days,
    DATE_DIFF('day', o.order_delivered_customer_date, o.order_estimated_delivery_date) AS delivery_vs_estimate_days
FROM stg_orders o;

CREATE OR REPLACE TABLE fact_order_items AS
SELECT
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.shipping_limit_date,
    oi.price,
    oi.freight_value,
    oi.price + oi.freight_value AS total_item_value
FROM stg_order_items oi;

CREATE OR REPLACE TABLE fact_payments AS
SELECT
    op.order_id,
    op.payment_sequential,
    op.payment_type,
    op.payment_installments,
    op.payment_value
FROM stg_order_payments op;

CREATE OR REPLACE TABLE fact_reviews AS
SELECT
    r.review_id,
    r.order_id,
    r.review_score,
    r.review_creation_date,
    r.review_answer_timestamp,
    DATE_DIFF('day', r.review_creation_date, r.review_answer_timestamp) AS answer_latency_days
FROM stg_order_reviews r;
"""


def build_warehouse(settings: Settings | None = None) -> Path:
    """Build (or rebuild) the DuckDB star schema. Returns the db file path."""
    settings = settings or get_settings()
    settings.ensure_dirs()
    db_path = settings.duckdb_file
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with timer("warehouse.build"):
        con = duckdb.connect(str(db_path))
        try:
            _register_staging(con, settings.processed_dir)
            con.execute(_DDL)
            counts = {
                t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in (
                    "dim_customers",
                    "dim_products",
                    "dim_sellers",
                    "dim_geography",
                    "dim_dates",
                    "fact_orders",
                    "fact_order_items",
                    "fact_payments",
                    "fact_reviews",
                )
            }
        finally:
            con.close()

    log.info("warehouse.build_done", db=str(db_path), row_counts=counts)
    return db_path


if __name__ == "__main__":  # pragma: no cover
    build_warehouse()
