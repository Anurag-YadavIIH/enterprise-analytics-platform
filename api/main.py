"""FastAPI application factory for the Olist Analytics API.

Exposes REST endpoints over the DuckDB star-schema warehouse:
``/kpis``, ``/revenue``, ``/customers``, ``/orders``, ``/products``,
``/dashboard`` plus ``/health``. Run with::

    uvicorn api.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.db import warehouse_exists
from api.routers import customers, dashboard, kpis, orders, products, revenue
from api.schemas import HealthResponse
from eap import __version__
from eap.config import get_settings
from eap.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("api")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=__version__,
        description="Analytics API over the Olist e-commerce star schema.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            warehouse_available=warehouse_exists(),
            version=__version__,
        )

    @app.get("/", tags=["meta"], summary="API index")
    def index() -> dict:
        return {
            "name": settings.api_title,
            "version": __version__,
            "docs": "/docs",
            "endpoints": ["/health", "/kpis", "/revenue/monthly", "/customers",
                          "/orders", "/products/top", "/dashboard"],
        }

    for module in (kpis, revenue, customers, orders, products, dashboard):
        app.include_router(module.router)

    log.info("api.ready", version=__version__)
    return app


app = create_app()
