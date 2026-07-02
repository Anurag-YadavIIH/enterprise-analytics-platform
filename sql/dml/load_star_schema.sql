-- =====================================================================
-- DML: load the star schema from staged raw tables inside Postgres.
-- Use when raw CSVs have been COPY'd into olist_raw.* (an alternative
-- to scripts/load_postgres.py, which loads from Parquet via Python).
--
-- Assumes raw tables exist as olist_raw.customers, olist_raw.orders, ...
-- with the original Olist column names.
-- =====================================================================
SET search_path TO olist, public;

BEGIN;

-- Dimensions ---------------------------------------------------------
INSERT INTO dim_customers
SELECT DISTINCT ON (customer_id)
       customer_id, customer_unique_id, customer_zip_code_prefix::int,
       lower(trim(customer_city)), upper(customer_state)
FROM olist_raw.customers
ORDER BY customer_id;

INSERT INTO dim_sellers
SELECT DISTINCT ON (seller_id)
       seller_id, seller_zip_code_prefix::int,
       lower(trim(seller_city)), upper(seller_state)
FROM olist_raw.sellers
ORDER BY seller_id;

INSERT INTO dim_products
SELECT DISTINCT ON (p.product_id)
       p.product_id,
       p.product_category_name,
       COALESCE(t.product_category_name_english, p.product_category_name),
       p.product_weight_g::numeric, p.product_length_cm::numeric,
       p.product_height_cm::numeric, p.product_width_cm::numeric,
       p.product_photos_qty::numeric
FROM olist_raw.products p
LEFT JOIN olist_raw.product_category_name_translation t
       ON p.product_category_name = t.product_category_name
ORDER BY p.product_id;

INSERT INTO dim_geography
SELECT geolocation_zip_code_prefix::int,
       AVG(geolocation_lat::numeric),
       AVG(geolocation_lng::numeric),
       MIN(geolocation_city),
       MIN(geolocation_state)
FROM olist_raw.geolocation
GROUP BY geolocation_zip_code_prefix;

INSERT INTO dim_dates
SELECT TO_CHAR(d, 'YYYYMMDD')::int,
       d::date,
       EXTRACT(year FROM d)::smallint,
       EXTRACT(quarter FROM d)::smallint,
       EXTRACT(month FROM d)::smallint,
       TO_CHAR(d, 'FMMonth'),
       EXTRACT(day FROM d)::smallint,
       EXTRACT(dow FROM d)::smallint,
       TO_CHAR(d, 'FMDay'),
       EXTRACT(week FROM d)::smallint,
       EXTRACT(dow FROM d) IN (0, 6)
FROM generate_series(
    (SELECT MIN(order_purchase_timestamp::date) FROM olist_raw.orders),
    (SELECT MAX(order_purchase_timestamp::date) FROM olist_raw.orders),
    interval '1 day'
) AS d;

-- Facts --------------------------------------------------------------
INSERT INTO fact_orders
SELECT DISTINCT ON (o.order_id)
       o.order_id, o.customer_id, o.order_status,
       o.order_purchase_timestamp::timestamp,
       TO_CHAR(o.order_purchase_timestamp::timestamp, 'YYYYMMDD')::int,
       NULLIF(o.order_approved_at, '')::timestamp,
       NULLIF(o.order_delivered_carrier_date, '')::timestamp,
       NULLIF(o.order_delivered_customer_date, '')::timestamp,
       NULLIF(o.order_estimated_delivery_date, '')::timestamp,
       EXTRACT(day FROM NULLIF(o.order_delivered_customer_date, '')::timestamp
                        - o.order_purchase_timestamp::timestamp)::int,
       EXTRACT(day FROM NULLIF(o.order_estimated_delivery_date, '')::timestamp
                        - NULLIF(o.order_delivered_customer_date, '')::timestamp)::int
FROM olist_raw.orders o
ORDER BY o.order_id;

INSERT INTO fact_order_items
SELECT order_id, order_item_id::int, product_id, seller_id,
       shipping_limit_date::timestamp,
       price::numeric, freight_value::numeric,
       price::numeric + freight_value::numeric
FROM olist_raw.order_items;

INSERT INTO fact_payments
SELECT order_id, payment_sequential::int, payment_type,
       payment_installments::int, payment_value::numeric
FROM olist_raw.order_payments;

INSERT INTO fact_reviews
SELECT DISTINCT ON (review_id)
       review_id, order_id, review_score::smallint,
       review_creation_date::timestamp,
       review_answer_timestamp::timestamp,
       EXTRACT(day FROM review_answer_timestamp::timestamp
                        - review_creation_date::timestamp)::int
FROM olist_raw.order_reviews
ORDER BY review_id;

COMMIT;

-- Sanity check
SELECT 'dim_customers' AS t, COUNT(*) FROM dim_customers
UNION ALL SELECT 'fact_orders', COUNT(*) FROM fact_orders
UNION ALL SELECT 'fact_order_items', COUNT(*) FROM fact_order_items;
