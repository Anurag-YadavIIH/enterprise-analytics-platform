-- =====================================================================
-- Olist Star Schema — PostgreSQL DDL
-- Mounted into the postgres container via docker-entrypoint-initdb.d.
-- Table names mirror the DuckDB warehouse so the query library is portable.
-- =====================================================================
SET client_min_messages = WARNING;

DROP SCHEMA IF EXISTS olist CASCADE;
CREATE SCHEMA olist;
SET search_path TO olist, public;

-- ---------------- Dimensions ----------------
CREATE TABLE dim_customers (
    customer_id              VARCHAR(50) PRIMARY KEY,
    customer_unique_id       VARCHAR(50) NOT NULL,
    customer_zip_code_prefix INTEGER,
    customer_city            VARCHAR(100),
    customer_state           CHAR(2)
);

CREATE TABLE dim_sellers (
    seller_id              VARCHAR(50) PRIMARY KEY,
    seller_zip_code_prefix INTEGER,
    seller_city            VARCHAR(100),
    seller_state           CHAR(2)
);

CREATE TABLE dim_products (
    product_id               VARCHAR(50) PRIMARY KEY,
    product_category_name    VARCHAR(100),
    product_category_english VARCHAR(100),
    product_weight_g         NUMERIC,
    product_length_cm        NUMERIC,
    product_height_cm        NUMERIC,
    product_width_cm         NUMERIC,
    product_photos_qty       NUMERIC
);

CREATE TABLE dim_geography (
    zip_code_prefix INTEGER PRIMARY KEY,
    latitude        NUMERIC,
    longitude       NUMERIC,
    city            VARCHAR(100),
    state           CHAR(2)
);

CREATE TABLE dim_dates (
    date_key      INTEGER PRIMARY KEY,   -- YYYYMMDD
    date          DATE NOT NULL,
    year          SMALLINT,
    quarter       SMALLINT,
    month         SMALLINT,
    month_name    VARCHAR(12),
    day           SMALLINT,
    day_of_week   SMALLINT,
    day_name      VARCHAR(12),
    week_of_year  SMALLINT,
    is_weekend    BOOLEAN
);

-- ---------------- Facts ----------------
CREATE TABLE fact_orders (
    order_id                      VARCHAR(50) PRIMARY KEY,
    customer_id                   VARCHAR(50) NOT NULL REFERENCES dim_customers(customer_id),
    order_status                  VARCHAR(20) NOT NULL,
    order_purchase_timestamp      TIMESTAMP,
    purchase_date_key             INTEGER REFERENCES dim_dates(date_key),
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP,
    delivery_days                 INTEGER,
    delivery_vs_estimate_days     INTEGER
);

CREATE TABLE fact_order_items (
    order_id            VARCHAR(50) NOT NULL REFERENCES fact_orders(order_id),
    order_item_id       INTEGER NOT NULL,
    product_id          VARCHAR(50) REFERENCES dim_products(product_id),
    seller_id           VARCHAR(50) REFERENCES dim_sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(12,2),
    freight_value       NUMERIC(12,2),
    total_item_value    NUMERIC(12,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE fact_payments (
    order_id             VARCHAR(50) NOT NULL REFERENCES fact_orders(order_id),
    payment_sequential   INTEGER NOT NULL,
    payment_type         VARCHAR(20),
    payment_installments INTEGER,
    payment_value        NUMERIC(12,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE fact_reviews (
    review_id               VARCHAR(50) PRIMARY KEY,
    order_id                VARCHAR(50) NOT NULL REFERENCES fact_orders(order_id),
    review_score            SMALLINT CHECK (review_score BETWEEN 1 AND 5),
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    answer_latency_days     INTEGER
);
