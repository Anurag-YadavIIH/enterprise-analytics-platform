"""API integration tests: real DuckDB warehouse behind a TestClient.

Marked ``integration`` because they exercise app wiring end-to-end, but they
still run anywhere (no network, no Docker).
"""

from __future__ import annotations

import pytest

from eap.config import Settings


@pytest.fixture(scope="module")
def client(warehouse: Settings):
    """TestClient wired to the session-scoped test warehouse."""
    import api.db as api_db
    from api.main import create_app
    from fastapi.testclient import TestClient

    # Point the API at the test warehouse (bypass cached global settings).
    original = api_db._warehouse_path
    api_db._warehouse_path = lambda: warehouse.duckdb_file  # type: ignore[assignment]
    try:
        yield TestClient(create_app())
    finally:
        api_db._warehouse_path = original  # type: ignore[assignment]


@pytest.mark.integration
def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["warehouse_available"] is True


@pytest.mark.integration
def test_kpis_values(client) -> None:
    body = client.get("/kpis").json()
    assert body["total_orders"] == 3
    assert body["total_revenue"] == pytest.approx(495.0)
    assert body["unique_customers"] == 3
    assert body["avg_review_score"] == pytest.approx(4.0)


@pytest.mark.integration
def test_monthly_revenue_delivered_only(client) -> None:
    rows = client.get("/revenue/monthly").json()
    periods = {r["period"]: r for r in rows}
    assert periods["2018-01"]["revenue"] == pytest.approx(165.0)
    assert periods["2018-02"]["revenue"] == pytest.approx(110.0)  # o3 not delivered


@pytest.mark.integration
def test_customer_search_and_detail(client) -> None:
    rows = client.get("/customers", params={"state": "MG"}).json()
    assert len(rows) == 1 and rows[0]["customer_id"] == "c3"

    detail = client.get("/customers/c1").json()
    assert detail["total_spent"] == pytest.approx(165.0)

    assert client.get("/customers/nope").status_code == 404


@pytest.mark.integration
def test_orders_filters_and_404(client) -> None:
    shipped = client.get("/orders", params={"status": "shipped"}).json()
    assert [o["order_id"] for o in shipped] == ["o3"]

    breakdown = {
        r["order_status"]: r["orders"] for r in client.get("/orders/status-breakdown").json()
    }
    assert breakdown == {"delivered": 2, "shipped": 1}

    assert client.get("/orders/ghost").status_code == 404


@pytest.mark.integration
def test_products_and_dashboard(client) -> None:
    cats = client.get("/products/categories").json()
    by_cat = {c["category"]: c for c in cats}
    assert by_cat["electronics"]["revenue"] == pytest.approx(250.0)
    assert by_cat["furniture"]["revenue"] == pytest.approx(200.0)

    dash = client.get("/dashboard").json()
    assert set(dash) == {"kpis", "monthly_orders", "top_categories"}
    assert dash["kpis"]["total_revenue"] == pytest.approx(495.0)
