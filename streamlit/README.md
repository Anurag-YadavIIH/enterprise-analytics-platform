# streamlit — Dashboard

Multi-page app over the DuckDB warehouse.

- `app.py` — Overview (KPIs, monthly revenue, states, categories)
- `pages/1_Analytics.py` — category deep-dive with filters
- `pages/2_Customer_Search.py` — filtered search + CSV export
- `pages/3_Forecast.py` — Holt-Winters projection (moving-average fallback)
- `data.py` — the only DB-touching module; all queries `st.cache_data`-cached

Run: `make app` → http://localhost:8501. Full guide: `docs/streamlit.md`.
