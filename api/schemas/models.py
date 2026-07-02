"""Pydantic response models for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    warehouse_available: bool
    version: str


class KPIResponse(BaseModel):
    total_orders: int
    total_revenue: float
    avg_order_value: float
    unique_customers: int
    avg_review_score: float | None = None
    on_time_delivery_rate: float | None = None


class RevenuePoint(BaseModel):
    period: str = Field(..., description="YYYY-MM period")
    revenue: float
    orders: int


class CustomerSummary(BaseModel):
    customer_id: str
    customer_unique_id: str
    customer_city: str | None = None
    customer_state: str | None = None
    orders: int
    total_spent: float


class ProductSummary(BaseModel):
    product_id: str
    category: str | None = None
    orders: int
    revenue: float


class OrderSummary(BaseModel):
    order_id: str
    customer_id: str
    order_status: str
    purchase_timestamp: str | None = None
    payment_value: float | None = None
    delivery_days: int | None = None


class Paginated(BaseModel):
    total: int
    limit: int
    offset: int
