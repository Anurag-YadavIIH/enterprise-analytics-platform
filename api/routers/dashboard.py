"""Aggregate dashboard endpoint combining several metrics in one payload."""

from __future__ import annotations

from fastapi import APIRouter

from api.db import query, query_one

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", summary="Combined dashboard payload")
def dashboard() -> dict:
    kpis = query_one("""
        SELECT COUNT(*) AS total_orders,
               COUNT(DISTINCT customer_id) AS unique_customers
        FROM fact_orders
    """) or {}
    revenue = query_one("SELECT ROUND(SUM(payment_value),2) AS total_revenue FROM fact_payments") or {}
    monthly = query("""
        SELECT strftime(order_purchase_timestamp, '%Y-%m') AS period,
               COUNT(*) AS orders
        FROM fact_orders GROUP BY 1 ORDER BY 1
    """)
    top_categories = query("""
        SELECT COALESCE(d.product_category_english,'unknown') AS category,
               ROUND(SUM(i.price),2) AS revenue
        FROM fact_order_items i
        LEFT JOIN dim_products d ON i.product_id = d.product_id
        GROUP BY 1 ORDER BY revenue DESC LIMIT 5
    """)
    return {
        "kpis": {**kpis, **revenue},
        "monthly_orders": monthly,
        "top_categories": top_categories,
    }
