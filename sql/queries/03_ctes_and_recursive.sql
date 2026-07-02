-- =====================================================================
-- SECTION 3 — CTEs & recursive CTEs (Q28–Q37)
-- Multi-step CTE pipelines, recursive date spines and hierarchies.
-- =====================================================================

-- Q28. Multi-CTE: high-value customers who also left low reviews.
WITH spend AS (
    SELECT c.customer_unique_id, SUM(p.payment_value) AS total_spent
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
),
reviews AS (
    SELECT c.customer_unique_id, AVG(r.review_score) AS avg_review
    FROM fact_reviews r
    JOIN fact_orders o ON r.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
threshold AS (
    SELECT PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY total_spent) AS p90 FROM spend
)
SELECT s.customer_unique_id, ROUND(s.total_spent, 2) AS total_spent,
       ROUND(r.avg_review, 2) AS avg_review
FROM spend s
JOIN reviews r ON s.customer_unique_id = r.customer_unique_id
CROSS JOIN threshold t
WHERE s.total_spent >= t.p90 AND r.avg_review <= 2
ORDER BY s.total_spent DESC;

-- Q29. Recursive CTE: dense calendar spine for the dataset date range.
WITH RECURSIVE bounds AS (
    SELECT CAST(MIN(order_purchase_timestamp) AS DATE) AS d,
           CAST(MAX(order_purchase_timestamp) AS DATE) AS d_max
    FROM fact_orders
),
calendar AS (
    SELECT d, d_max FROM bounds
    UNION ALL
    SELECT d + INTERVAL 1 DAY, d_max FROM calendar WHERE d < d_max
)
SELECT COUNT(*) AS days_in_range, MIN(d) AS first_day, MAX(d) AS last_day
FROM calendar;

-- Q30. Recursive CTE: fill revenue gaps so every month appears (zero-filled).
WITH RECURSIVE bounds AS (
    SELECT DATE_TRUNC('month', MIN(order_purchase_timestamp)) AS m,
           DATE_TRUNC('month', MAX(order_purchase_timestamp)) AS m_max
    FROM fact_orders
),
months AS (
    SELECT m, m_max FROM bounds
    UNION ALL
    SELECT m + INTERVAL 1 MONTH, m_max FROM months WHERE m < m_max
),
actual AS (
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS m,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY 1
)
SELECT months.m AS month,
       ROUND(COALESCE(actual.revenue, 0), 2) AS revenue
FROM months
LEFT JOIN actual ON months.m = actual.m
ORDER BY month;

-- Q31. CTE pipeline: order -> category -> category revenue share of grand total.
WITH order_cat AS (
    SELECT i.order_id, d.product_category_english AS category, i.price
    FROM fact_order_items i
    JOIN dim_products d ON i.product_id = d.product_id
),
cat_rev AS (
    SELECT category, SUM(price) AS revenue FROM order_cat GROUP BY category
),
total AS (
    SELECT SUM(revenue) AS grand_total FROM cat_rev
)
SELECT c.category, ROUND(c.revenue, 2) AS revenue,
       ROUND(100.0 * c.revenue / t.grand_total, 2) AS pct_of_total
FROM cat_rev c CROSS JOIN total t
ORDER BY revenue DESC
LIMIT 20;

-- Q32. Recursive CTE: numbers 1..12 to label a month-of-year template.
WITH RECURSIVE m(n) AS (
    SELECT 1
    UNION ALL
    SELECT n + 1 FROM m WHERE n < 12
)
SELECT n AS month_number FROM m ORDER BY n;

-- Q33. CTE: customers whose second order was larger than their first.
WITH ordered AS (
    SELECT c.customer_unique_id, o.order_id, o.order_purchase_timestamp,
           SUM(p.payment_value) AS order_value,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp) AS seq
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id, o.order_id, o.order_purchase_timestamp
),
first_two AS (
    SELECT customer_unique_id,
           MAX(CASE WHEN seq = 1 THEN order_value END) AS first_value,
           MAX(CASE WHEN seq = 2 THEN order_value END) AS second_value
    FROM ordered
    WHERE seq <= 2
    GROUP BY customer_unique_id
)
SELECT customer_unique_id,
       ROUND(first_value, 2)  AS first_value,
       ROUND(second_value, 2) AS second_value
FROM first_two
WHERE second_value IS NOT NULL AND second_value > first_value
ORDER BY second_value DESC;

-- Q34. CTE: state-level KPI table (orders, revenue, AOV, avg review).
WITH base AS (
    SELECT c.customer_state AS state, o.order_id,
           SUM(p.payment_value) AS order_value
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_state, o.order_id
),
rev AS (
    SELECT state, COUNT(*) AS orders, SUM(order_value) AS revenue,
           AVG(order_value) AS aov
    FROM base GROUP BY state
),
rev_score AS (
    SELECT c.customer_state AS state, AVG(r.review_score) AS avg_review
    FROM fact_reviews r
    JOIN fact_orders o ON r.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_state
)
SELECT rev.state, rev.orders,
       ROUND(rev.revenue, 2) AS revenue,
       ROUND(rev.aov, 2) AS aov,
       ROUND(rev_score.avg_review, 2) AS avg_review
FROM rev
LEFT JOIN rev_score ON rev.state = rev_score.state
ORDER BY revenue DESC;

-- Q35. CTE: identify one-time vs repeat customers and their revenue split.
WITH orders_per AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS n_orders,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT CASE WHEN n_orders = 1 THEN 'one_time' ELSE 'repeat' END AS segment,
       COUNT(*) AS customers,
       ROUND(SUM(revenue), 2) AS revenue,
       ROUND(100.0 * SUM(revenue) / SUM(SUM(revenue)) OVER (), 2) AS pct_revenue
FROM orders_per
GROUP BY 1;

-- Q36. Recursive CTE: cumulative "streak" of consecutive active months (platform-wide).
WITH monthly AS (
    SELECT DISTINCT DATE_TRUNC('month', order_purchase_timestamp) AS m
    FROM fact_orders
),
ranked AS (
    SELECT m, ROW_NUMBER() OVER (ORDER BY m) AS rn FROM monthly
)
SELECT MIN(m) AS streak_start, MAX(m) AS streak_end, COUNT(*) AS months
FROM ranked;  -- single continuous stream here (a gap-and-island template)

-- Q37. CTE: average basket composition (items per order, distinct products per order).
WITH basket AS (
    SELECT order_id,
           COUNT(*) AS items,
           COUNT(DISTINCT product_id) AS distinct_products,
           SUM(price) AS items_value
    FROM fact_order_items
    GROUP BY order_id
)
SELECT ROUND(AVG(items), 2) AS avg_items,
       ROUND(AVG(distinct_products), 2) AS avg_distinct_products,
       ROUND(AVG(items_value), 2) AS avg_items_value
FROM basket;
