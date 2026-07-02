-- =====================================================================
-- SECTION 1 — Aggregation & business fundamentals (Q1–Q12)
-- Schema: olist star schema (dim_*, fact_*). Runs on DuckDB & PostgreSQL.
-- Every query is preceded by the business question it answers.
-- =====================================================================

-- Q1. Total delivered revenue and order count (headline KPI).
SELECT COUNT(DISTINCT o.order_id) AS delivered_orders,
       ROUND(SUM(p.payment_value), 2) AS revenue
FROM fact_orders o
JOIN fact_payments p ON o.order_id = p.order_id
WHERE o.order_status = 'delivered';

-- Q2. Average order value (AOV) overall.
SELECT ROUND(SUM(payment_value) / COUNT(DISTINCT order_id), 2) AS aov
FROM fact_payments;

-- Q3. Orders and revenue by order status.
SELECT o.order_status,
       COUNT(*) AS orders,
       ROUND(COALESCE(SUM(p.payment_value), 0), 2) AS revenue
FROM fact_orders o
LEFT JOIN fact_payments p ON o.order_id = p.order_id
GROUP BY o.order_status
ORDER BY orders DESC;

-- Q4. Revenue by customer state (top 10).
SELECT c.customer_state,
       ROUND(SUM(p.payment_value), 2) AS revenue
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
JOIN fact_payments p ON o.order_id = p.order_id
GROUP BY c.customer_state
ORDER BY revenue DESC
LIMIT 10;

-- Q5. Payment-type mix (share of transactions and value).
SELECT payment_type,
       COUNT(*) AS payments,
       ROUND(SUM(payment_value), 2) AS value,
       ROUND(100.0 * SUM(payment_value) / SUM(SUM(payment_value)) OVER (), 2) AS pct_value
FROM fact_payments
GROUP BY payment_type
ORDER BY value DESC;

-- Q6. Average installments by payment type.
SELECT payment_type, ROUND(AVG(payment_installments), 2) AS avg_installments
FROM fact_payments
WHERE payment_installments > 0
GROUP BY payment_type
ORDER BY avg_installments DESC;

-- Q7. Top 10 product categories by revenue.
SELECT COALESCE(d.product_category_english, 'unknown') AS category,
       ROUND(SUM(i.price), 2) AS revenue,
       COUNT(DISTINCT i.order_id) AS orders
FROM fact_order_items i
LEFT JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1
ORDER BY revenue DESC
LIMIT 10;

-- Q8. Freight as a percentage of item revenue by category.
SELECT COALESCE(d.product_category_english, 'unknown') AS category,
       ROUND(100.0 * SUM(i.freight_value) / NULLIF(SUM(i.price), 0), 2) AS freight_pct
FROM fact_order_items i
LEFT JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1
ORDER BY freight_pct DESC
LIMIT 15;

-- Q9. Average review score by state.
SELECT c.customer_state,
       ROUND(AVG(r.review_score), 3) AS avg_review
FROM fact_reviews r
JOIN fact_orders o ON r.order_id = o.order_id
JOIN dim_customers c ON o.customer_id = c.customer_id
GROUP BY c.customer_state
ORDER BY avg_review DESC;

-- Q10. On-time delivery rate (delivered on or before estimate).
SELECT ROUND(100.0 * AVG(CASE WHEN delivery_vs_estimate_days >= 0 THEN 1 ELSE 0 END), 2) AS on_time_pct
FROM fact_orders
WHERE order_status = 'delivered' AND delivery_vs_estimate_days IS NOT NULL;

-- Q11. Average delivery time (days) by state.
SELECT c.customer_state, ROUND(AVG(o.delivery_days), 2) AS avg_delivery_days
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WHERE o.delivery_days IS NOT NULL
GROUP BY c.customer_state
ORDER BY avg_delivery_days;

-- Q12. Multi-item order rate (share of orders with >1 item).
SELECT ROUND(100.0 * AVG(CASE WHEN item_count > 1 THEN 1 ELSE 0 END), 2) AS multi_item_pct
FROM (
    SELECT order_id, COUNT(*) AS item_count
    FROM fact_order_items GROUP BY order_id
) t;
