# api — FastAPI Service

Read-only REST API over the DuckDB star schema.

- `main.py` — app factory, CORS, `/health`, router registration
- `db.py` — short-lived read-only connections, parameterised query helpers
- `routers/` — kpis · revenue · customers · orders · products · dashboard
- `schemas/` — pydantic response models

Run: `make api` → http://localhost:8000/docs. Full guide: `docs/api.md`.
