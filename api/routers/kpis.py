"""Top-level business KPIs."""

from __future__ import annotations

from fastapi import APIRouter

from api.db import query_one
from api.schemas import KPIResponse

router = APIRouter(prefix="/kpis", tags=["kpis"])

_KPI_SQL = """
WITH order_value AS (
    SELECT o.order_id, o.customer_id, o.order_status,
           COALESCE(p.payment_value, 0) AS payment_value,
           o.delivery_days,
           o.delivery_vs_estimate_days
    FROM fact_orders o
    LEFT JOIN (
        SELECT order_id, SUM(payment_value) AS payment_value
        FROM fact_payments GROUP BY order_id
    ) p ON o.order_id = p.order_id
)
SELECT
    COUNT(*)                                              AS total_orders,
    ROUND(SUM(payment_value), 2)                          AS total_revenue,
    ROUND(AVG(payment_value), 2)                          AS avg_order_value,
    COUNT(DISTINCT customer_id)                           AS unique_customers,
    (SELECT ROUND(AVG(review_score), 3) FROM fact_reviews) AS avg_review_score,
    ROUND(AVG(CASE WHEN delivery_vs_estimate_days >= 0 THEN 1.0 ELSE 0.0 END), 4)
                                                          AS on_time_delivery_rate
FROM order_value
"""


@router.get("", response_model=KPIResponse, summary="Headline KPIs")
def get_kpis() -> KPIResponse:
    row = query_one(_KPI_SQL) or {}
    return KPIResponse(**row)
