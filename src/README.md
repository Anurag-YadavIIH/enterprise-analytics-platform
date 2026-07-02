# src/eap — Platform Core

Installable Python package (`pip install -e .`) exposing the `eap` CLI.

| Module | Purpose |
|---|---|
| `config/settings.py` | Typed env-driven settings (pydantic-settings), cached via `get_settings()` |
| `config/catalog.py` | **Single source of schema truth**: keys, timestamps, numerics per table |
| `ingestion/` | Kaggle/local acquisition + pandas cleaning to Parquet |
| `quality/` | Fast validation engine + Great Expectations suite builder |
| `warehouse/` | DuckDB star-schema builder |
| `utils/` | structlog logging, timers, Parquet IO |
| `cli.py` | `eap ingest|spark|warehouse|quality|pipeline` |

Everything is import-safe without heavy optional deps (Spark/GE/dbt load lazily).
