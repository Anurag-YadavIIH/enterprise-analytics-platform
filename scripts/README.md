# scripts

- `load_postgres.py` — load the star schema into PostgreSQL from the DuckDB
  build (guarantees both warehouses are identical). Flags: `--truncate`,
  `--chunksize`.
