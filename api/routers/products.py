"""Product endpoints: top products and category rollups."""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.db import query
from api.schemas import ProductSummary

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/top", response_model=list[ProductSummary], summary="Top products by revenue")
def top_products(limit: int = Query(10, ge=1, le=100)) -> list[ProductSummary]:
    sql = """
    SELECT i.product_id,
           d.product_category_english AS category,
           COUNT(DISTINCT i.order_id) AS orders,
           ROUND(SUM(i.price), 2) AS revenue
    FROM fact_order_items i
    LEFT JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2 ORDER BY revenue DESC LIMIT ?
    """
    return [ProductSummary(**r) for r in query(sql, [limit])]


@router.get("/categories", summary="Revenue by product category")
def categories(limit: int = Query(15, ge=1, le=100)) -> list[dict]:
    sql = """
    SELECT COALESCE(d.product_category_english, 'unknown') AS category,
           COUNT(DISTINCT i.order_id) AS orders,
           ROUND(SUM(i.price), 2) AS revenue,
           ROUND(AVG(i.price), 2) AS avg_item_price
    FROM fact_order_items i
    LEFT JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1 ORDER BY revenue DESC LIMIT ?
    """
    return query(sql, [limit])
