# API Guide

FastAPI service exposing the star schema as REST endpoints.

## Run

```bash
# Local
make warehouse            # ensure olist.duckdb exists
make api                  # uvicorn on :8000

# Docker
docker compose up -d api
```

Interactive docs: http://localhost:8000/docs (Swagger) and `/redoc`.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness + warehouse availability |
| GET | `/kpis` | Headline KPIs (orders, revenue, AOV, review, on-time %) |
| GET | `/revenue/monthly` | Delivered revenue time series |
| GET | `/revenue/by-state?limit=` | Revenue by customer state |
| GET | `/customers?state=&city=&limit=&offset=` | Customer search |
| GET | `/customers/{id}` | Single customer summary |
| GET | `/orders?status=&limit=&offset=` | Order list |
| GET | `/orders/status-breakdown` | Counts per status |
| GET | `/orders/{id}` | Single order |
| GET | `/products/top?limit=` | Top products by revenue |
| GET | `/products/categories?limit=` | Category rollup |
| GET | `/dashboard` | Combined payload for dashboards |

## Examples

```bash
curl -s localhost:8000/kpis | jq
curl -s "localhost:8000/customers?state=SP&limit=5" | jq
curl -s "localhost:8000/orders?status=delivered&limit=3" | jq
```

## Design notes

- **Read-only DuckDB**: every request opens a short-lived read-only
  connection (`api/db.py`), so the API can never corrupt the warehouse and
  the pipeline can rebuild it safely.
- **Parameterised SQL only** — no string interpolation of user input.
- **Pydantic response models** (`api/schemas/models.py`) give a typed,
  self-documenting contract.
- 404s for unknown customer/order IDs; all list endpoints are paginated.
