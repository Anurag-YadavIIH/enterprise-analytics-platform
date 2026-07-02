# Excel Guide

Two supported paths for analysts who live in Excel.

## Path 1 — Power Query over Parquet (recommended)

1. Run the pipeline: `make pipeline` (produces `data/processed/*.parquet`).
2. Excel → *Data* → *Get Data* → *From File* → *From Parquet*.
3. Load `orders.parquet`, `order_items.parquet`, `order_payments.parquet`,
   `products.parquet`, `customers.parquet`.
4. In Power Query, merge:
   - `order_items` ← `products` on `product_id` (bring in category)
   - `orders` ← `customers` on `customer_id` (bring in state)
5. *Close & Load To…* → *Only Create Connection* + *Add to Data Model*.

## Path 2 — CSV extract from the reporting DAG

The Airflow reporting DAG (or a manual run of
`python -c "…export_extracts…"`) writes
`data/warehouse/monthly_revenue_extract.csv` — a small, always-fresh extract
for lightweight workbooks.

## Pivot-table starter pack (Data Model)

| Analysis | Rows | Values | Filter |
|---|---|---|---|
| Monthly revenue | order month (from `order_purchase_timestamp`) | Sum of `payment_value` | `order_status = delivered` |
| Category performance | `product_category_name` | Sum of `price`, Count of `order_id` | — |
| State revenue | `customer_state` | Sum of `payment_value` | — |
| Payment mix | `payment_type` | Sum of `payment_value`, Avg of `payment_installments` | — |

## Useful formulas on flat extracts

```text
AOV                =SUMIFS(payments[payment_value],...)/COUNTIFS(orders[order_id],...)
On-time flag       =IF([@delivery_vs_estimate_days]>=0,1,0)
Order month        =TEXT([@order_purchase_timestamp],"YYYY-MM")
Spend tier         =IFS([@total]<100,"Low",[@total]<300,"Mid",[@total]<1000,"High",TRUE,"VIP")
```

Keep workbook logic thin: anything reusable belongs in dbt marts or the SQL
library so every tool reports the same numbers.
