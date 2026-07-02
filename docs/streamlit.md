# Streamlit Dashboard Guide

Multi-page analytics app reading the DuckDB warehouse directly.

## Run

```bash
make warehouse   # ensure data/warehouse/olist.duckdb exists
make app         # streamlit run streamlit/app.py -> http://localhost:8501
# or: docker compose up -d streamlit
```

## Pages

| Page | What it shows |
|---|---|
| **Overview** (`app.py`) | KPI metric row, monthly revenue line, revenue-by-state bar, top categories |
| **1 · Analytics** | Category deep-dive with Top-N slider and revenue/orders toggle, state table |
| **2 · Customer Search** | State filter + min-spend slider, results grid, CSV download |
| **3 · Forecast** | Holt-Winters revenue projection with adjustable horizon (moving-average fallback) |

## How it's built

- `streamlit/data.py` is the only module that touches the database. Each
  query is a small cached function (`st.cache_data`), so page code stays
  declarative and re-renders are instant.
- Charts are Plotly Express for hover/zoom interactivity.
- The forecast degrades gracefully: with <6 months of history (or without
  statsmodels installed) it falls back to a moving average instead of erroring.

## Extending

Add a file to `streamlit/pages/` (e.g. `4_Sellers.py`); Streamlit picks it up
automatically. Add any new query to `data.py` with `@st.cache_data`.
