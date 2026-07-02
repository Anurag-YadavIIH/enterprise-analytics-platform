# Power BI Guide

How to connect Power BI Desktop to the platform and rebuild the executive
dashboard.

## 1. Connect

**Option A — PostgreSQL (recommended for a live model)**
1. `docker compose up -d postgres` and load data: `python scripts/load_postgres.py`.
2. Power BI Desktop → *Get Data* → *PostgreSQL database*.
3. Server `localhost:5432`, database `olist`. Credentials from your `.env`
   (defaults `analytics` / `analytics`).
4. Select the `olist` schema tables: `dim_customers`, `dim_products`,
   `dim_sellers`, `dim_dates`, `fact_orders`, `fact_order_items`,
   `fact_payments`, `fact_reviews`.

**Option B — Parquet import (no database needed)**
*Get Data* → *Parquet* → point at the files in `data/processed/` or the
partitioned outputs in `data/parquet/`.

## 2. Model relationships

Create single-direction (dimension → fact) relationships:

| From | To | Cardinality |
|---|---|---|
| `dim_customers[customer_id]` | `fact_orders[customer_id]` | 1:* |
| `dim_dates[date_key]` | `fact_orders[purchase_date_key]` | 1:* |
| `fact_orders[order_id]` | `fact_order_items[order_id]` | 1:* |
| `fact_orders[order_id]` | `fact_payments[order_id]` | 1:* |
| `fact_orders[order_id]` | `fact_reviews[order_id]` | 1:* |
| `dim_products[product_id]` | `fact_order_items[product_id]` | 1:* |
| `dim_sellers[seller_id]` | `fact_order_items[seller_id]` | 1:* |

Mark `dim_dates` as the model's *date table*.

## 3. Core DAX measures

```dax
Total Revenue = SUM ( fact_payments[payment_value] )

Total Orders = DISTINCTCOUNT ( fact_orders[order_id] )

Avg Order Value = DIVIDE ( [Total Revenue], [Total Orders] )

Delivered Revenue =
CALCULATE ( [Total Revenue], fact_orders[order_status] = "delivered" )

Revenue MoM % =
VAR Prev = CALCULATE ( [Total Revenue], DATEADD ( dim_dates[date], -1, MONTH ) )
RETURN DIVIDE ( [Total Revenue] - Prev, Prev )

On-Time Delivery % =
VAR OnTime =
    CALCULATE (
        [Total Orders],
        fact_orders[delivery_vs_estimate_days] >= 0
    )
RETURN DIVIDE ( OnTime, [Total Orders] )

Avg Review Score = AVERAGE ( fact_reviews[review_score] )

Repeat Customer % =
VAR Repeats =
    COUNTROWS (
        FILTER (
            SUMMARIZE ( fact_orders, dim_customers[customer_unique_id],
                        "n", DISTINCTCOUNT ( fact_orders[order_id] ) ),
            [n] > 1
        )
    )
RETURN DIVIDE ( Repeats, DISTINCTCOUNT ( dim_customers[customer_unique_id] ) )
```

## 4. Suggested report pages

1. **Executive Overview** — KPI cards (Revenue, Orders, AOV, Review, On-Time %),
   monthly revenue line, revenue-by-state filled map.
2. **Product & Category** — category bar chart, ABC-class table (mirror
   `sql/queries/07`), price vs freight scatter.
3. **Customers** — RFM segment matrix (mirror `sql/queries/06`), new vs
   returning revenue, cohort retention heatmap (mirror `sql/queries/05`).
4. **Delivery & Ops** — delivery-days distribution, on-time trend,
   status funnel.

Use the SQL library in `sql/queries/` as the reference logic for every visual —
each query documents the business question it answers.
