-- =====================================================================
-- Reusable analytical views.
-- =====================================================================
SET search_path TO olist, public;

-- One row per order with revenue, payment and review context.
CREATE OR REPLACE VIEW vw_order_facts AS
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp,
    DATE_TRUNC('month', o.order_purchase_timestamp)::date AS order_month,
    o.delivery_days,
    o.delivery_vs_estimate_days,
    p.payment_value,
    r.review_score
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
LEFT JOIN (
    SELECT order_id, SUM(payment_value) AS payment_value
    FROM fact_payments GROUP BY order_id
) p ON o.order_id = p.order_id
LEFT JOIN (
    SELECT order_id, AVG(review_score) AS review_score
    FROM fact_reviews GROUP BY order_id
) r ON o.order_id = r.order_id;

-- Monthly revenue KPI view.
CREATE OR REPLACE VIEW vw_monthly_revenue AS
SELECT
    DATE_TRUNC('month', order_purchase_timestamp)::date AS order_month,
    COUNT(DISTINCT order_id) AS orders,
    ROUND(SUM(payment_value), 2) AS revenue
FROM vw_order_facts
WHERE order_status = 'delivered'
GROUP BY 1;

-- Product performance view.
CREATE OR REPLACE VIEW vw_product_performance AS
SELECT
    d.product_id,
    d.product_category_english AS category,
    COUNT(DISTINCT i.order_id) AS orders,
    ROUND(SUM(i.price), 2)     AS revenue,
    ROUND(AVG(i.price), 2)     AS avg_price
FROM fact_order_items i
LEFT JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1, 2;
