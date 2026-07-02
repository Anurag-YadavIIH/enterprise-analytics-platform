# sql — Warehouse SQL Assets

```
ddl/         01_schema.sql (star schema) · 02_indexes.sql · 03_views.sql
dml/         load_star_schema.sql (in-database load from staged raw tables)
procedures/  functions, materialised-snapshot procedure, audit trigger, txn example
queries/     78-query analytical library (Q1–Q78), 7 themed files
```

- Postgres DDL auto-applies on `docker compose up` (initdb mount).
- Table names are identical in DuckDB, so **every query runs on both engines**.
- Each query begins with a `-- Qn. <business question>` comment.
- Alternative to `dml/`: `python scripts/load_postgres.py` loads from Parquet.
