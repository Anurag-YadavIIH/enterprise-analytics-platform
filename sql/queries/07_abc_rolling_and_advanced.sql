-- =====================================================================
-- SECTION 7 — ABC analysis, rolling metrics & advanced patterns (Q67–Q78)
-- ABC/Pareto classification, rolling windows, pivots, funnels, gap-and-island.
-- =====================================================================

-- Q67. ABC classification of products (A=top 80%, B=next 15%, C=last 5%).
WITH prod AS (
    SELECT i.product_id, SUM(i.price) AS revenue
    FROM fact_order_items i
    GROUP BY i.product_id
),
cum AS (
    SELECT product_id, revenue,
           SUM(revenue) OVER (ORDER BY revenue DESC) AS running,
           SUM(revenue) OVER () AS total
    FROM prod
)
SELECT product_id, ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * running / total, 2) AS cum_pct,
       CASE
           WHEN running <= 0.80 * total THEN 'A'
           WHEN running <= 0.95 * total THEN 'B'
           ELSE 'C'
       END AS abc_class
FROM cum
ORDER BY revenue DESC
LIMIT 40;

-- Q68. ABC class summary: count and revenue share per class.
WITH prod AS (
    SELECT i.product_id, SUM(i.price) AS revenue
    FROM fact_order_items i GROUP BY i.product_id
),
cum AS (
    SELECT product_id, revenue,
           SUM(revenue) OVER (ORDER BY revenue DESC) AS running,
           SUM(revenue) OVER () AS total
    FROM prod
),
classified AS (
    SELECT revenue, total,
           CASE WHEN running <= 0.80 * total THEN 'A'
                WHEN running <= 0.95 * total THEN 'B'
                ELSE 'C' END AS abc_class
    FROM cum
)
SELECT abc_class,
       COUNT(*) AS products,
       ROUND(SUM(revenue), 2) AS revenue,
       ROUND(100.0 * SUM(revenue) / MAX(total), 2) AS pct_revenue
FROM classified
GROUP BY abc_class
ORDER BY abc_class;

-- Q69. 7-day rolling revenue (daily grain).
WITH daily AS (
    SELECT CAST(o.order_purchase_timestamp AS DATE) AS d,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY 1
)
SELECT d, ROUND(revenue, 2) AS revenue,
       ROUND(AVG(revenue) OVER (ORDER BY d ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)
           AS rolling_7d_avg
FROM daily
ORDER BY d
LIMIT 60;

-- Q70. 30-day rolling distinct active customers.
WITH daily AS (
    SELECT CAST(o.order_purchase_timestamp AS DATE) AS d,
           c.customer_unique_id
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY 1, 2
),
counts AS (
    SELECT d, COUNT(DISTINCT customer_unique_id) AS active FROM daily GROUP BY d
)
SELECT d, active,
       SUM(active) OVER (ORDER BY d ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS active_30d
FROM counts
ORDER BY d
LIMIT 60;

-- Q71. Pivot: revenue by payment type across years (conditional aggregation).
SELECT EXTRACT(year FROM o.order_purchase_timestamp) AS yr,
       ROUND(SUM(CASE WHEN p.payment_type = 'credit_card' THEN p.payment_value ELSE 0 END), 2) AS credit_card,
       ROUND(SUM(CASE WHEN p.payment_type = 'boleto'      THEN p.payment_value ELSE 0 END), 2) AS boleto,
       ROUND(SUM(CASE WHEN p.payment_type = 'voucher'     THEN p.payment_value ELSE 0 END), 2) AS voucher,
       ROUND(SUM(CASE WHEN p.payment_type = 'debit_card'  THEN p.payment_value ELSE 0 END), 2) AS debit_card
FROM fact_payments p
JOIN fact_orders o ON p.order_id = o.order_id
GROUP BY 1
ORDER BY 1;

-- Q72. Delivery-performance funnel by status stage counts.
SELECT
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE order_approved_at IS NOT NULL) AS approved,
    COUNT(*) FILTER (WHERE order_delivered_carrier_date IS NOT NULL) AS shipped,
    COUNT(*) FILTER (WHERE order_delivered_customer_date IS NOT NULL) AS delivered
FROM fact_orders;

-- Q73. Basket-value distribution buckets (histogram).
WITH ov AS (
    SELECT order_id, SUM(payment_value) AS v FROM fact_payments GROUP BY order_id
)
SELECT CASE
           WHEN v < 50 THEN '1: <50'
           WHEN v < 100 THEN '2: 50-100'
           WHEN v < 200 THEN '3: 100-200'
           WHEN v < 500 THEN '4: 200-500'
           ELSE '5: 500+'
       END AS bucket,
       COUNT(*) AS orders,
       ROUND(SUM(v), 2) AS revenue
FROM ov
GROUP BY 1
ORDER BY 1;

-- Q74. Contribution margin proxy: price minus freight by category.
SELECT d.product_category_english AS category,
       ROUND(SUM(i.price), 2) AS gross_revenue,
       ROUND(SUM(i.freight_value), 2) AS freight_cost,
       ROUND(SUM(i.price) - SUM(i.freight_value), 2) AS net_after_freight,
       ROUND(100.0 * (SUM(i.price) - SUM(i.freight_value)) / NULLIF(SUM(i.price), 0), 2) AS margin_pct
FROM fact_order_items i
JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1
ORDER BY net_after_freight DESC
LIMIT 20;

-- Q75. Weekend vs weekday revenue and order comparison.
SELECT CASE WHEN EXTRACT(dow FROM o.order_purchase_timestamp) IN (0, 6)
            THEN 'weekend' ELSE 'weekday' END AS day_type,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(p.payment_value), 2) AS revenue,
       ROUND(AVG(p.payment_value), 2) AS avg_payment
FROM fact_orders o
JOIN fact_payments p ON o.order_id = p.order_id
GROUP BY 1;

-- Q76. Hour-of-day order pattern (peak shopping hours).
SELECT EXTRACT(hour FROM order_purchase_timestamp) AS hour_of_day,
       COUNT(*) AS orders
FROM fact_orders
GROUP BY 1
ORDER BY 1;

-- Q77. Review-score impact on repeat purchasing (does a bad first review reduce repeats?).
WITH first_order AS (
    SELECT c.customer_unique_id, o.order_id,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp) AS seq
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
),
first_review AS (
    SELECT f.customer_unique_id, AVG(r.review_score) AS first_review
    FROM first_order f
    JOIN fact_reviews r ON f.order_id = r.order_id
    WHERE f.seq = 1
    GROUP BY f.customer_unique_id
),
totals AS (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
)
SELECT ROUND(fr.first_review) AS first_review_score,
       COUNT(*) AS customers,
       ROUND(AVG(t.n_orders), 3) AS avg_total_orders,
       ROUND(100.0 * AVG(CASE WHEN t.n_orders > 1 THEN 1 ELSE 0 END), 2) AS repeat_rate_pct
FROM first_review fr
JOIN totals t ON fr.customer_unique_id = t.customer_unique_id
GROUP BY 1
ORDER BY 1;

-- Q78. Seller performance scorecard: revenue, orders, avg review, avg delivery.
SELECT s.seller_id, s.seller_state,
       COUNT(DISTINCT i.order_id) AS orders,
       ROUND(SUM(i.price), 2) AS revenue,
       ROUND(AVG(r.review_score), 2) AS avg_review,
       ROUND(AVG(o.delivery_days), 1) AS avg_delivery_days
FROM fact_order_items i
JOIN dim_sellers s ON i.seller_id = s.seller_id
JOIN fact_orders o ON i.order_id = o.order_id
LEFT JOIN fact_reviews r ON o.order_id = r.order_id
GROUP BY s.seller_id, s.seller_state
HAVING COUNT(DISTINCT i.order_id) >= 5
ORDER BY revenue DESC
LIMIT 25;
