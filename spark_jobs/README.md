# spark_jobs — PySpark Layer

| Job | What it does |
|---|---|
| `session.py` | Shared SparkSession factory: AQE, tuned shuffle partitions, Arrow, snappy |
| `csv_to_parquet.py` | Raw CSV → cleaned Parquet, schema-driven from the eap catalog; `orders` partitioned by year/month |
| `transformations.py` | Broadcast-join dims, aggregate items/payments to order grain, write `fact_orders_enriched` |
| `run_all.py` | Orchestrates both jobs (used by `eap spark run-all` and Airflow) |

Run locally: `eap spark run-all` (requires `pip install -e ".[spark]"`).
The pandas ingestion in `src/eap/ingestion` is the reference implementation;
both read the same catalog so cleaning semantics stay identical.
