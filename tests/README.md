# tests

- `conftest.py` builds an isolated synthetic Olist dataset per session
  (includes an intentional duplicate PK and empty timestamps).
- `unit/` — catalog invariants, ingestion cleaning/dedup, quality engine
  (incl. injected FK violation), warehouse star-schema correctness.
- `integration/` — every API endpoint against a real DuckDB warehouse.

Run: `pytest` (25 tests). Markers: `-m unit`, `-m integration`.
