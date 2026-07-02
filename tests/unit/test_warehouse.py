"""Warehouse builder: star schema correctness."""

import duckdb
import pytest

from eap.config import Settings


@pytest.mark.unit
def test_all_star_tables_exist(warehouse: Settings) -> None:
    con = duckdb.connect(str(warehouse.duckdb_file), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    expected = {
        "dim_customers", "dim_products", "dim_sellers", "dim_geography",
        "dim_dates", "fact_orders", "fact_order_items", "fact_payments",
        "fact_reviews",
    }
    assert expected.issubset(tables)


@pytest.mark.unit
def test_fact_orders_metrics(warehouse: Settings) -> None:
    con = duckdb.connect(str(warehouse.duckdb_file), read_only=True)
    try:
        n, gmv = con.execute(
            """
            SELECT (SELECT COUNT(*) FROM fact_orders),
                   (SELECT SUM(total_item_value) FROM fact_order_items)
            """
        ).fetchone()
    finally:
        con.close()
    assert n == 3
    assert gmv == pytest.approx(495.0)


@pytest.mark.unit
def test_dim_dates_covers_order_range(warehouse: Settings) -> None:
    con = duckdb.connect(str(warehouse.duckdb_file), read_only=True)
    try:
        lo, hi, n = con.execute(
            "SELECT MIN(date), MAX(date), COUNT(*) FROM dim_dates"
        ).fetchone()
    finally:
        con.close()
    assert str(lo) == "2018-01-05"
    assert str(hi) == "2018-02-11"
    assert n == 38  # inclusive daily spine


@pytest.mark.unit
def test_category_translation_applied(warehouse: Settings) -> None:
    con = duckdb.connect(str(warehouse.duckdb_file), read_only=True)
    try:
        cats = {
            r[0]
            for r in con.execute(
                "SELECT DISTINCT product_category_english FROM dim_products"
            ).fetchall()
        }
    finally:
        con.close()
    assert cats == {"furniture", "electronics"}
