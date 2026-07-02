"""Customer endpoints: search + per-customer summary."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.db import query, query_one
from api.schemas import CustomerSummary

router = APIRouter(prefix="/customers", tags=["customers"])

_BASE = """
SELECT c.customer_id, c.customer_unique_id, c.customer_city, c.customer_state,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(COALESCE(SUM(p.payment_value), 0), 2) AS total_spent
FROM dim_customers c
LEFT JOIN fact_orders o ON c.customer_id = o.customer_id
LEFT JOIN (SELECT order_id, SUM(payment_value) AS payment_value
           FROM fact_payments GROUP BY order_id) p ON o.order_id = p.order_id
"""


@router.get("", response_model=list[CustomerSummary], summary="Search customers")
def list_customers(
    state: str | None = Query(None, description="Filter by 2-letter state code"),
    city: str | None = Query(None, description="Filter by city (case-insensitive)"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[CustomerSummary]:
    where, params = [], []
    if state:
        where.append("c.customer_state = ?")
        params.append(state.upper())
    if city:
        where.append("lower(c.customer_city) = lower(?)")
        params.append(city)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"{_BASE} {clause} GROUP BY 1,2,3,4 ORDER BY total_spent DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    return [CustomerSummary(**r) for r in query(sql, params)]


@router.get("/{customer_id}", response_model=CustomerSummary, summary="Customer by id")
def get_customer(customer_id: str) -> CustomerSummary:
    sql = f"{_BASE} WHERE c.customer_id = ? GROUP BY 1,2,3,4"
    row = query_one(sql, [customer_id])
    if not row:
        raise HTTPException(status_code=404, detail="customer not found")
    return CustomerSummary(**row)
