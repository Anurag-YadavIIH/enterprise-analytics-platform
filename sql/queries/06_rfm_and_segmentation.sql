-- =====================================================================
-- SECTION 6 — RFM & customer segmentation (Q58–Q66)
-- Recency / Frequency / Monetary scoring and named segments.
-- =====================================================================

-- Q58. Raw RFM metrics per customer (recency vs latest data date).
WITH ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders),
rfm AS (
    SELECT c.customer_unique_id,
           DATE_DIFF('day', MAX(o.order_purchase_timestamp),
                     (SELECT max_ts FROM ref)) AS recency_days,
           COUNT(DISTINCT o.order_id) AS frequency,
           SUM(p.payment_value) AS monetary
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT customer_unique_id, recency_days, frequency,
       ROUND(monetary, 2) AS monetary
FROM rfm
ORDER BY monetary DESC
LIMIT 25;

-- Q59. RFM quintile scores (1–5) using NTILE.
WITH ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders),
rfm AS (
    SELECT c.customer_unique_id,
           DATE_DIFF('day', MAX(o.order_purchase_timestamp),
                     (SELECT max_ts FROM ref)) AS recency_days,
           COUNT(DISTINCT o.order_id) AS frequency,
           SUM(p.payment_value) AS monetary
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT customer_unique_id, recency_days, frequency, ROUND(monetary, 2) AS monetary,
       -- customer_unique_id is a deterministic tie-breaker: recency/frequency/monetary
       -- have heavy ties (e.g. most customers have frequency=1), and NTILE's tie
       -- handling is otherwise unstable across runs without a fully-ordered key.
       6 - NTILE(5) OVER (ORDER BY recency_days, customer_unique_id) AS r_score,  -- lower recency = better
       NTILE(5) OVER (ORDER BY frequency, customer_unique_id)        AS f_score,
       NTILE(5) OVER (ORDER BY monetary, customer_unique_id)         AS m_score
FROM rfm
ORDER BY monetary DESC
LIMIT 25;

-- Q60. Named RFM segments (Champions, Loyal, At-Risk, Hibernating, ...).
WITH ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders),
rfm AS (
    SELECT c.customer_unique_id,
           DATE_DIFF('day', MAX(o.order_purchase_timestamp),
                     (SELECT max_ts FROM ref)) AS recency_days,
           COUNT(DISTINCT o.order_id) AS frequency,
           SUM(p.payment_value) AS monetary
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
),
scored AS (
    -- customer_unique_id is a deterministic tie-breaker (see Q59 for why).
    SELECT customer_unique_id,
           6 - NTILE(5) OVER (ORDER BY recency_days, customer_unique_id) AS r,
           NTILE(5) OVER (ORDER BY frequency, customer_unique_id)        AS f,
           NTILE(5) OVER (ORDER BY monetary, customer_unique_id)         AS m
    FROM rfm
)
SELECT
    CASE
        WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
        WHEN r >= 4 AND f >= 3            THEN 'Loyal'
        WHEN r >= 4 AND f <= 2            THEN 'New / Promising'
        WHEN r = 3                        THEN 'Needs Attention'
        WHEN r <= 2 AND f >= 4            THEN 'At Risk'
        WHEN r <= 2 AND m >= 4            THEN 'Cannot Lose Them'
        ELSE 'Hibernating'
    END AS segment,
    COUNT(*) AS customers
FROM scored
GROUP BY 1
ORDER BY customers DESC;

-- Q61. Revenue contribution by RFM monetary quintile.
WITH rfm AS (
    SELECT c.customer_unique_id, SUM(p.payment_value) AS monetary
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
),
scored AS (
    -- customer_unique_id is a deterministic tie-breaker (see Q59 for why).
    SELECT customer_unique_id, monetary,
           NTILE(5) OVER (ORDER BY monetary, customer_unique_id) AS m_quintile
    FROM rfm
)
SELECT m_quintile,
       COUNT(*) AS customers,
       ROUND(SUM(monetary), 2) AS revenue,
       ROUND(100.0 * SUM(monetary) / SUM(SUM(monetary)) OVER (), 2) AS pct_revenue
FROM scored
GROUP BY m_quintile
ORDER BY m_quintile DESC;

-- Q62. Spend-tier segmentation (Low / Mid / High / VIP by fixed thresholds).
WITH cust AS (
    SELECT c.customer_unique_id, SUM(p.payment_value) AS total_spent
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT CASE
           WHEN total_spent < 100  THEN '1_Low (<100)'
           WHEN total_spent < 300  THEN '2_Mid (100-300)'
           WHEN total_spent < 1000 THEN '3_High (300-1000)'
           ELSE '4_VIP (1000+)'
       END AS tier,
       COUNT(*) AS customers,
       ROUND(SUM(total_spent), 2) AS revenue
FROM cust
GROUP BY 1
ORDER BY 1;

-- Q63. Frequency segmentation crossed with average review.
WITH cust AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS orders,
           AVG(r.review_score) AS avg_review
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    LEFT JOIN fact_reviews r ON o.order_id = r.order_id
    GROUP BY c.customer_unique_id
)
SELECT CASE WHEN orders = 1 THEN 'single' WHEN orders <= 3 THEN '2-3' ELSE '4+' END AS freq_band,
       COUNT(*) AS customers,
       ROUND(AVG(avg_review), 3) AS avg_review
FROM cust
GROUP BY 1
ORDER BY 1;

-- Q64. Geographic segmentation: revenue concentration by region (state prefix).
SELECT c.customer_state,
       COUNT(DISTINCT c.customer_unique_id) AS customers,
       ROUND(SUM(p.payment_value), 2) AS revenue,
       ROUND(SUM(p.payment_value) / COUNT(DISTINCT c.customer_unique_id), 2) AS revenue_per_customer
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
JOIN fact_payments p ON o.order_id = p.order_id
GROUP BY c.customer_state
ORDER BY revenue DESC;

-- Q65. Cross-sell affinity: categories frequently bought by the same customer.
WITH cust_cat AS (
    SELECT DISTINCT c.customer_unique_id, d.product_category_english AS category
    FROM fact_order_items i
    JOIN fact_orders o ON i.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN dim_products d ON i.product_id = d.product_id
)
SELECT a.category AS category_a, b.category AS category_b,
       COUNT(*) AS shared_customers
FROM cust_cat a
JOIN cust_cat b ON a.customer_unique_id = b.customer_unique_id
                AND a.category < b.category
GROUP BY 1, 2
ORDER BY shared_customers DESC
LIMIT 20;

-- Q66. Single-purchase customers with high AOV (win-back targets).
WITH cust AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS orders,
           SUM(p.payment_value) AS total_spent
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT customer_unique_id, ROUND(total_spent, 2) AS total_spent
FROM cust
WHERE orders = 1 AND total_spent > (SELECT AVG(total_spent) * 2 FROM cust)
ORDER BY total_spent DESC
LIMIT 25;
