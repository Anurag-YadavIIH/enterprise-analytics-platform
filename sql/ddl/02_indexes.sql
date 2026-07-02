-- =====================================================================
-- Indexes to support the analytical query library.
-- =====================================================================
SET search_path TO olist, public;

-- Foreign-key / join accelerators
CREATE INDEX idx_orders_customer      ON fact_orders (customer_id);
CREATE INDEX idx_orders_status        ON fact_orders (order_status);
CREATE INDEX idx_orders_purchase_ts   ON fact_orders (order_purchase_timestamp);
CREATE INDEX idx_orders_date_key      ON fact_orders (purchase_date_key);

CREATE INDEX idx_items_product        ON fact_order_items (product_id);
CREATE INDEX idx_items_seller         ON fact_order_items (seller_id);
CREATE INDEX idx_items_order          ON fact_order_items (order_id);

CREATE INDEX idx_payments_order       ON fact_payments (order_id);
CREATE INDEX idx_payments_type        ON fact_payments (payment_type);

CREATE INDEX idx_reviews_order        ON fact_reviews (order_id);
CREATE INDEX idx_reviews_score        ON fact_reviews (review_score);

CREATE INDEX idx_customers_state      ON dim_customers (customer_state);
CREATE INDEX idx_customers_unique     ON dim_customers (customer_unique_id);
CREATE INDEX idx_products_category    ON dim_products (product_category_english);

-- Covering index for the monthly-revenue rollup
CREATE INDEX idx_orders_status_ts     ON fact_orders (order_status, order_purchase_timestamp);
