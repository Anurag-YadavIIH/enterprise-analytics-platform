# dbt — Transformation Layer

Project: `olist/` (profile targets: `duckdb` default, `postgres`).

```
models/staging/        7 stg_* views + sources.yml (reads processed Parquet)
models/intermediate/   order-grain aggregations (payments, items, reviews)
models/marts/core/     dim_customers, dim_products, dim_sellers, fact_orders
models/marts/finance/  fct_monthly_revenue, fct_revenue_by_state
models/marts/marketing/fct_customer_rfm, fct_category_performance
seeds/                 state_regions.csv (Brazilian state → region)
macros/                cents_to_reais, custom generate_schema_name
tests/                 assert_positive_revenue (singular)
```

Run: `cd dbt/olist && DBT_PROFILES_DIR=. dbt build`
(verified: 1 seed, 8 tables, 10 views, 18 tests — PASS=37 ERROR=0).
