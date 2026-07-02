"""Order endpoints: list/filter orders and status breakdown."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.db import query, query_one
from api.schemas import OrderSummary

router = APIRouter(prefix="/orders", tags=["orders"])

_BASE = """
SELECT o.order_id, o.customer_id, o.order_status,
       CAST(o.order_purchase_timestamp AS VARCHAR) AS purchase_timestamp,
       ROUND(p.payment_value, 2) AS payment_value,
       o.delivery_days
FROM fact_orders o
LEFT JOIN (SELECT order_id, SUM(payment_value) AS payment_value
           FROM fact_payments GROUP BY order_id) p ON o.order_id = p.order_id
"""


@router.get("", response_model=list[OrderSummary], summary="List orders")
def list_orders(
    status: str | None = Query(None, description="Filter by order_status"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[OrderSummary]:
    where, params = [], []
    if status:
        where.append("o.order_status = ?")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"{_BASE} {clause} ORDER BY o.order_purchase_timestamp DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return [OrderSummary(**r) for r in query(sql, params)]


@router.get("/status-breakdown", summary="Order counts by status")
def status_breakdown() -> list[dict]:
    return query("SELECT order_status, COUNT(*) AS orders FROM fact_orders GROUP BY 1 ORDER BY orders DESC")


@router.get("/{order_id}", response_model=OrderSummary, summary="Order by id")
def get_order(order_id: str) -> OrderSummary:
    row = query_one(f"{_BASE} WHERE o.order_id = ?", [order_id])
    if not row:
        raise HTTPException(status_code=404, detail="order not found")
    return OrderSummary(**row)
