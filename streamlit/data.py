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
def avg_order_value() -> float:
    df = run_query("SELECT SUM(payment_value) / COUNT(DISTINCT order_id) AS aov FROM fact_payments")
    return float(df.iloc[0, 0] or 0)


@st.cache_data(show_spinner=False)
def delivery_retention() -> pd.DataFrame:
    """Repeat-purchase rate and LTV split by whether a customer's first order arrived late."""
    return run_query(
        """
        WITH first_order AS (
            SELECT c.customer_unique_id,
                   o.order_id,
                   o.delivery_vs_estimate_days,
                   ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                                      ORDER BY o.order_purchase_timestamp) AS seq
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            WHERE o.order_delivered_customer_date IS NOT NULL
        ),
        first_only AS (
            SELECT customer_unique_id,
                   CASE WHEN delivery_vs_estimate_days < 0 THEN 'late' ELSE 'on_time' END AS first_delivery_status
            FROM first_order WHERE seq = 1
        ),
        cust_stats AS (
            SELECT c.customer_unique_id,
                   COUNT(DISTINCT o.order_id) AS total_orders,
                   SUM(p.payment_value) AS ltv
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            JOIN fact_payments p ON o.order_id = p.order_id
            GROUP BY c.customer_unique_id
        )
        SELECT f.first_delivery_status,
               COUNT(*) AS customers,
               ROUND(100.0 * AVG(CASE WHEN cs.total_orders > 1 THEN 1 ELSE 0 END), 2) AS repeat_rate_pct,
               ROUND(AVG(cs.ltv), 2) AS avg_ltv
        FROM first_only f
        JOIN cust_stats cs ON f.customer_unique_id = cs.customer_unique_id
        GROUP BY f.first_delivery_status
        """
    )


@st.cache_data(show_spinner=False)
def late_delivery_by_state() -> pd.DataFrame:
    """Late-delivery rate by customer state (states with < 30 delivered orders excluded)."""
    return run_query(
        """
        SELECT c.customer_state,
               COUNT(*) AS delivered_orders,
               COUNT(*) FILTER (WHERE o.delivery_vs_estimate_days < 0) AS late_orders,
               ROUND(100.0 * COUNT(*) FILTER (WHERE o.delivery_vs_estimate_days < 0) / COUNT(*), 2) AS late_pct
        FROM fact_orders o
        JOIN dim_customers c ON o.customer_id = c.customer_id
        WHERE o.order_delivered_customer_date IS NOT NULL
        GROUP BY c.customer_state
        HAVING COUNT(*) >= 30
        ORDER BY late_pct DESC
        """
    )


@st.cache_data(show_spinner=False)
def freight_by_category() -> pd.DataFrame:
    """Freight burden (freight as % of price) by product category, nationally."""
    return run_query(
        """
        SELECT COALESCE(d.product_category_english, 'unknown') AS category,
               COUNT(*) AS items,
               ROUND(AVG(i.price), 2) AS avg_price,
               ROUND(AVG(i.freight_value), 2) AS avg_freight,
               ROUND(100.0 * AVG(i.freight_value) / NULLIF(AVG(i.price), 0), 2) AS freight_pct_of_price
        FROM fact_order_items i
        LEFT JOIN dim_products d ON i.product_id = d.product_id
        GROUP BY 1
        HAVING COUNT(*) >= 20
        ORDER BY freight_pct_of_price DESC
        """
    )


@st.cache_data(show_spinner=False)
def freight_by_category_region() -> pd.DataFrame:
    """Freight burden by category x customer state (cells with < 20 items excluded)."""
    return run_query(
        """
        SELECT COALESCE(d.product_category_english, 'unknown') AS category,
               c.customer_state,
               COUNT(*) AS items,
               ROUND(AVG(i.price), 2) AS avg_price,
               ROUND(AVG(i.freight_value), 2) AS avg_freight,
               ROUND(100.0 * AVG(i.freight_value) / NULLIF(AVG(i.price), 0), 2) AS freight_pct_of_price
        FROM fact_order_items i
        JOIN fact_orders o ON i.order_id = o.order_id
        JOIN dim_customers c ON o.customer_id = c.customer_id
        LEFT JOIN dim_products d ON i.product_id = d.product_id
        GROUP BY 1, 2
        HAVING COUNT(*) >= 20
        ORDER BY freight_pct_of_price DESC
        """
    )


@st.cache_data(show_spinner=False)
def rfm_winback_list() -> pd.DataFrame:
    """Named "At Risk" / "Cannot Lose Them" customers (segment defs match sql/queries/06)."""
    return run_query(
        """
        WITH ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders),
        rfm AS (
            SELECT c.customer_unique_id,
                   DATE_DIFF('day', MAX(o.order_purchase_timestamp), (SELECT max_ts FROM ref)) AS recency_days,
                   COUNT(DISTINCT o.order_id) AS frequency,
                   SUM(p.payment_value) AS monetary
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            JOIN fact_payments p ON o.order_id = p.order_id
            GROUP BY c.customer_unique_id
        ),
        scored AS (
            -- customer_unique_id is a deterministic tie-breaker: recency/frequency/
            -- monetary have heavy ties, and NTILE's tie handling is otherwise unstable
            -- across runs without a fully-ordered key.
            SELECT customer_unique_id, recency_days, frequency, monetary,
                   6 - NTILE(5) OVER (ORDER BY recency_days, customer_unique_id) AS r,
                   NTILE(5) OVER (ORDER BY frequency, customer_unique_id)        AS f,
                   NTILE(5) OVER (ORDER BY monetary, customer_unique_id)         AS m
            FROM rfm
        ),
        segmented AS (
            SELECT *,
                CASE
                    WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
                    WHEN r >= 4 AND f >= 3            THEN 'Loyal'
                    WHEN r >= 4 AND f <= 2            THEN 'New / Promising'
                    WHEN r = 3                        THEN 'Needs Attention'
                    WHEN r <= 2 AND f >= 4            THEN 'At Risk'
                    WHEN r <= 2 AND m >= 4            THEN 'Cannot Lose Them'
                    ELSE 'Hibernating'
                END AS segment
            FROM scored
        )
        SELECT customer_unique_id, segment, recency_days, frequency, ROUND(monetary, 2) AS monetary
        FROM segmented
        WHERE segment IN ('At Risk', 'Cannot Lose Them')
        ORDER BY monetary DESC
        """
    )


@st.cache_data(show_spinner=False)
def payback_curve() -> pd.DataFrame:
    """Cumulative revenue per customer by months since acquisition, pooled across all cohorts."""
    return run_query(
        """
        WITH first_order AS (
            SELECT c.customer_unique_id, MIN(o.order_purchase_timestamp) AS first_ts
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            GROUP BY c.customer_unique_id
        ),
        cohort_size AS (SELECT COUNT(*) AS n_customers FROM first_order),
        order_rev AS (
            SELECT c.customer_unique_id,
                   DATE_DIFF('month', f.first_ts, o.order_purchase_timestamp) AS months_since_first_order,
                   SUM(p.payment_value) AS revenue
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            JOIN fact_payments p ON o.order_id = p.order_id
            JOIN first_order f ON c.customer_unique_id = f.customer_unique_id
            GROUP BY 1, 2
        )
        SELECT months_since_first_order,
               ROUND(SUM(revenue), 2) AS total_revenue,
               ROUND(SUM(revenue) / (SELECT n_customers FROM cohort_size), 2) AS revenue_per_customer,
               ROUND(SUM(SUM(revenue)) OVER (ORDER BY months_since_first_order)
                     / (SELECT n_customers FROM cohort_size), 2) AS cumulative_revenue_per_customer
        FROM order_rev
        GROUP BY months_since_first_order
        ORDER BY months_since_first_order
        """
    )


@st.cache_data(show_spinner=False)
def geo_opportunity() -> pd.DataFrame:
    """Revenue-per-customer vs. average delivery days, by state (states with < 30 customers excluded)."""
    return run_query(
        """
        SELECT c.customer_state,
               COUNT(DISTINCT c.customer_unique_id) AS customers,
               ROUND(SUM(p.payment_value) / COUNT(DISTINCT c.customer_unique_id), 2) AS revenue_per_customer,
               ROUND(AVG(o.delivery_days), 1) AS avg_delivery_days
        FROM fact_orders o
        JOIN dim_customers c ON o.customer_id = c.customer_id
        JOIN fact_payments p ON o.order_id = p.order_id
        WHERE o.delivery_days IS NOT NULL
        GROUP BY c.customer_state
        HAVING COUNT(DISTINCT c.customer_unique_id) >= 30
        ORDER BY revenue_per_customer DESC
        """
    )


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
