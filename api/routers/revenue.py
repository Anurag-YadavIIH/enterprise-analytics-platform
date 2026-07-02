"""Revenue time series and breakdowns."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.db import query
from api.schemas import RevenuePoint

router = APIRouter(prefix="/revenue", tags=["revenue"])

_MONTHLY_SQL = """
SELECT
    strftime(o.order_purchase_timestamp, '%Y-%m') AS period,
    ROUND(SUM(p.payment_value), 2)                AS revenue,
    COUNT(DISTINCT o.order_id)                    AS orders
FROM fact_orders o
JOIN (
    SELECT order_id, SUM(payment_value) AS payment_value
    FROM fact_payments GROUP BY order_id
) p ON o.order_id = p.order_id
WHERE o.order_status = 'delivered'
GROUP BY 1
ORDER BY 1
"""


@router.get("/monthly", response_model=list[RevenuePoint], summary="Monthly revenue")
def monthly_revenue() -> list[RevenuePoint]:
    return [RevenuePoint(**r) for r in query(_MONTHLY_SQL)]


@router.get("/by-state", summary="Revenue by customer state")
def revenue_by_state(limit: int = Query(10, ge=1, le=50)) -> list[dict]:
    sql = """
    SELECT c.customer_state AS state,
           ROUND(SUM(p.payment_value), 2) AS revenue,
           COUNT(DISTINCT o.order_id) AS orders
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN (SELECT order_id, SUM(payment_value) AS payment_value
          FROM fact_payments GROUP BY order_id) p ON o.order_id = p.order_id
    GROUP BY 1 ORDER BY revenue DESC LIMIT ?
    """
    return query(sql, [limit])
