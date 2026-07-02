# airflow — Orchestration

| DAG | Schedule | Purpose |
|---|---|---|
| `olist_pipeline` | daily 04:00 | Master: download → ingest → spark → warehouse → dbt → quality |
| `olist_ingestion` | every 6h | Acquire + clean raw data (TaskFlow API) |
| `olist_data_quality` | daily 04:30 | Validate Parquet; raises on any failed check |
| `olist_reporting` | daily 05:00 | Rebuild warehouse + export BI extracts |

DAGs are intentionally thin — they call the tested `eap` package/CLI.
Run in Docker: `docker compose up -d airflow` → http://localhost:8080
(admin/admin by default; change via `.env`).
