# Star Schema — ER Diagram

The warehouse models Olist as a classic star schema: conformed dimensions
around four fact tables at different grains.

```mermaid
erDiagram
    DIM_CUSTOMERS {
        varchar customer_id PK
        varchar customer_unique_id
        int     customer_zip_code_prefix
        varchar customer_city
        char2   customer_state
    }

    DIM_SELLERS {
        varchar seller_id PK
        int     seller_zip_code_prefix
        varchar seller_city
        char2   seller_state
    }

    DIM_PRODUCTS {
        varchar product_id PK
        varchar product_category_name
        varchar product_category_english
        numeric product_weight_g
        numeric product_length_cm
        numeric product_height_cm
        numeric product_width_cm
        numeric product_photos_qty
    }

    DIM_GEOGRAPHY {
        int     zip_code_prefix PK
        numeric latitude
        numeric longitude
        varchar city
        char2   state
    }

    DIM_DATES {
        int      date_key PK "YYYYMMDD"
        date     date
        smallint year
        smallint quarter
        smallint month
        varchar  month_name
        smallint day
        smallint day_of_week
        varchar  day_name
        smallint week_of_year
        boolean  is_weekend
    }

    FACT_ORDERS {
        varchar   order_id PK
        varchar   customer_id FK
        varchar   order_status
        timestamp order_purchase_timestamp
        int       purchase_date_key FK
        timestamp order_approved_at
        timestamp order_delivered_carrier_date
        timestamp order_delivered_customer_date
        timestamp order_estimated_delivery_date
        int       delivery_days
        int       delivery_vs_estimate_days
    }

    FACT_ORDER_ITEMS {
        varchar   order_id PK, FK
        int       order_item_id PK
        varchar   product_id FK
        varchar   seller_id FK
        timestamp shipping_limit_date
        numeric   price
        numeric   freight_value
        numeric   total_item_value
    }

    FACT_PAYMENTS {
        varchar order_id PK, FK
        int     payment_sequential PK
        varchar payment_type
        int     payment_installments
        numeric payment_value
    }

    FACT_REVIEWS {
        varchar   review_id PK
        varchar   order_id FK
        smallint  review_score "1..5 CHECK"
        timestamp review_creation_date
        timestamp review_answer_timestamp
        int       answer_latency_days
    }

    DIM_CUSTOMERS ||--o{ FACT_ORDERS : "places"
    DIM_DATES     ||--o{ FACT_ORDERS : "purchase date"
    FACT_ORDERS   ||--|{ FACT_ORDER_ITEMS : "contains"
    FACT_ORDERS   ||--|{ FACT_PAYMENTS : "paid by"
    FACT_ORDERS   ||--o{ FACT_REVIEWS : "reviewed by"
    DIM_PRODUCTS  ||--o{ FACT_ORDER_ITEMS : "sold as"
    DIM_SELLERS   ||--o{ FACT_ORDER_ITEMS : "fulfilled by"
    DIM_GEOGRAPHY ||--o{ DIM_CUSTOMERS : "located in (zip prefix)"
    DIM_GEOGRAPHY ||--o{ DIM_SELLERS : "located in (zip prefix)"
```

## Grain of each fact

| Fact | Grain | Typical questions |
|---|---|---|
| `fact_orders` | one row per order | delivery SLAs, status funnels, order counts |
| `fact_order_items` | one row per order line | product & seller revenue, freight economics |
| `fact_payments` | one row per payment attempt | payment mix, installments, revenue |
| `fact_reviews` | one row per review | CSAT, review latency, score drivers |

Physical DDL: [`sql/ddl/01_schema.sql`](../sql/ddl/01_schema.sql) (PostgreSQL) and
the embedded DDL in [`src/eap/warehouse/build.py`](../src/eap/warehouse/build.py) (DuckDB).
