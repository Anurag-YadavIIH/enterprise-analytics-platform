"""Data access for the Streamlit app.

Reads directly from the DuckDB warehouse (fast, no network). Results are
cached with ``st.cache_data`` so re-renders are cheap. Every query is a small
function returning a DataFrame, keeping the page code declarative.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from eap.config import get_settings


def _connect() -> duckdb.DuckDBPyConnection:
    path = get_settings().duckdb_file
    if not path.exists():
        raise FileNotFoundError(
            f"Warehouse not found at {path}. Run `make pipeline` (or `eap warehouse build`)."
        )
    return duckdb.connect(str(path), read_only=True)


@st.cache_data(show_spinner=False)
def run_query(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = _connect()
    try:
        return con.execute(sql, list(params)).fetchdf()
    finally:
        con.close()


@st.cache_data(show_spinner=False)
def kpis() -> dict:
    df = run_query(
        """
        SELECT COUNT(*) AS total_orders,
               COUNT(DISTINCT customer_id) AS unique_customers
        FROM fact_orders
        """
    )
    rev = run_query("SELECT ROUND(SUM(payment_value),2) AS total_revenue FROM fact_payments")
    reviews = run_query("SELECT ROUND(AVG(review_score),3) AS avg_review FROM fact_reviews")
    row = df.iloc[0].to_dict()
    row["total_revenue"] = float(rev.iloc[0, 0] or 0)
    row["avg_review"] = float(reviews.iloc[0, 0] or 0)
    row["avg_order_value"] = round(
        row["total_revenue"] / row["total_orders"] if row["total_orders"] else 0, 2
    )
    return row


@st.cache_data(show_spinner=False)
def monthly_revenue() -> pd.DataFrame:
    return run_query(
        """
        SELECT strftime(o.order_purchase_timestamp, '%Y-%m') AS period,
               ROUND(SUM(p.payment_value),2) AS revenue,
               COUNT(DISTINCT o.order_id) AS orders
        FROM fact_orders o
        JOIN (SELECT order_id, SUM(payment_value) AS payment_value
              FROM fact_payments GROUP BY order_id) p ON o.order_id = p.order_id
        GROUP BY 1 ORDER BY 1
        """
    )


@st.cache_data(show_spinner=False)
def revenue_by_state() -> pd.DataFrame:
    return run_query(
        """
        SELECT c.customer_state AS state,
               ROUND(SUM(p.payment_value),2) AS revenue,
               COUNT(DISTINCT o.order_id) AS orders
        FROM fact_orders o
        JOIN dim_customers c ON o.customer_id = c.customer_id
        JOIN (SELECT order_id, SUM(payment_value) AS payment_value
              FROM fact_payments GROUP BY order_id) p ON o.order_id = p.order_id
        GROUP BY 1 ORDER BY revenue DESC
        """
    )


@st.cache_data(show_spinner=False)
def category_revenue() -> pd.DataFrame:
    return run_query(
        """
        SELECT COALESCE(d.product_category_english,'unknown') AS category,
               ROUND(SUM(i.price),2) AS revenue,
               COUNT(DISTINCT i.order_id) AS orders
        FROM fact_order_items i
        LEFT JOIN dim_products d ON i.product_id = d.product_id
        GROUP BY 1 ORDER BY revenue DESC
        """
    )


@st.cache_data(show_spinner=False)
def states() -> list[str]:
    df = run_query("SELECT DISTINCT customer_state FROM dim_customers ORDER BY 1")
    return df["customer_state"].dropna().tolist()


@st.cache_data(show_spinner=False)
def search_customers(state: str | None, min_spent: float) -> pd.DataFrame:
    sql = """
        SELECT c.customer_id, c.customer_city, c.customer_state,
               COUNT(DISTINCT o.order_id) AS orders,
               ROUND(COALESCE(SUM(p.payment_value),0),2) AS total_spent
        FROM dim_customers c
        LEFT JOIN fact_orders o ON c.customer_id = o.customer_id
        LEFT JOIN (SELECT order_id, SUM(payment_value) AS payment_value
                   FROM fact_payments GROUP BY order_id) p ON o.order_id = p.order_id
        {where}
        GROUP BY 1,2,3
        HAVING total_spent >= ?
        ORDER BY total_spent DESC
        LIMIT 500
    """
    if state and state != "All":
        return run_query(sql.format(where="WHERE c.customer_state = ?"), (state, min_spent))
    return run_query(sql.format(where=""), (min_spent,))
