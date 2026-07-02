-- =====================================================================
-- SECTION 4 — Ranking & Top-N patterns (Q38–Q47)
-- Greatest-n-per-group, ties, gaps, and Pareto-style leaderboards.
-- =====================================================================

-- Q38. Top 10 customers by lifetime value.
SELECT c.customer_unique_id,
       COUNT(DISTINCT o.order_id) AS orders,
       ROUND(SUM(p.payment_value), 2) AS ltv
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
JOIN fact_payments p ON o.order_id = p.order_id
GROUP BY c.customer_unique_id
ORDER BY ltv DESC
LIMIT 10;

-- Q39. Top seller in each state by revenue (greatest-n-per-group = 1).
WITH seller_state AS (
    SELECT s.seller_state AS state, i.seller_id,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN dim_sellers s ON i.seller_id = s.seller_id
    GROUP BY 1, 2
)
SELECT state, seller_id, ROUND(revenue, 2) AS revenue
FROM (
    SELECT state, seller_id, revenue,
           ROW_NUMBER() OVER (PARTITION BY state ORDER BY revenue DESC) AS rn
    FROM seller_state
) t
WHERE rn = 1
ORDER BY revenue DESC;

-- Q40. Bottom 10 categories by revenue (with at least 5 orders).
SELECT d.product_category_english AS category,
       COUNT(DISTINCT i.order_id) AS orders,
       ROUND(SUM(i.price), 2) AS revenue
FROM fact_order_items i
JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1
HAVING COUNT(DISTINCT i.order_id) >= 5
ORDER BY revenue ASC
LIMIT 10;

-- Q41. Top 5 orders by value per month.
WITH order_val AS (
    SELECT o.order_id,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(p.payment_value) AS order_value
    FROM fact_orders o
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY o.order_id, 2
)
SELECT month, order_id, ROUND(order_value, 2) AS order_value, rn
FROM (
    SELECT month, order_id, order_value,
           ROW_NUMBER() OVER (PARTITION BY month ORDER BY order_value DESC) AS rn
    FROM order_val
) t
WHERE rn <= 5
ORDER BY month, rn;

-- Q42. Pareto: how many categories make up 80% of revenue?
WITH cat AS (
    SELECT d.product_category_english AS category, SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1
),
cum AS (
    SELECT category, revenue,
           SUM(revenue) OVER (ORDER BY revenue DESC) AS running,
           SUM(revenue) OVER () AS total
    FROM cat
)
SELECT category, ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * running / total, 2) AS cumulative_pct
FROM cum
WHERE running <= 0.8 * total
ORDER BY revenue DESC;

-- Q43. Rank states by average review, showing ties (RANK).
WITH s AS (
    SELECT c.customer_state AS state, AVG(r.review_score) AS avg_review
    FROM fact_reviews r
    JOIN fact_orders o ON r.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_state
)
SELECT state, ROUND(avg_review, 3) AS avg_review,
       RANK() OVER (ORDER BY avg_review DESC) AS review_rank
FROM s
ORDER BY review_rank;

-- Q44. Most expensive product per category (by average item price).
WITH p AS (
    SELECT d.product_category_english AS category, i.product_id,
           AVG(i.price) AS avg_price
    FROM fact_order_items i
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2
)
SELECT category, product_id, ROUND(avg_price, 2) AS avg_price
FROM (
    SELECT category, product_id, avg_price,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY avg_price DESC) AS rn
    FROM p
) t
WHERE rn = 1
ORDER BY avg_price DESC
LIMIT 20;

-- Q45. Top 3 payment types by value per state.
WITH ps AS (
    SELECT c.customer_state AS state, pay.payment_type,
           SUM(pay.payment_value) AS value
    FROM fact_payments pay
    JOIN fact_orders o ON pay.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY 1, 2
)
SELECT state, payment_type, ROUND(value, 2) AS value
FROM (
    SELECT state, payment_type, value,
           DENSE_RANK() OVER (PARTITION BY state ORDER BY value DESC) AS rnk
    FROM ps
) t
WHERE rnk <= 3
ORDER BY state, value DESC;

-- Q46. Sellers ranked into deciles by revenue (NTILE 10).
WITH seller_rev AS (
    SELECT seller_id, SUM(price) AS revenue
    FROM fact_order_items GROUP BY seller_id
)
SELECT decile,
       COUNT(*) AS sellers,
       ROUND(SUM(revenue), 2) AS revenue
FROM (
    SELECT revenue, NTILE(10) OVER (ORDER BY revenue DESC) AS decile
    FROM seller_rev
) d
GROUP BY decile
ORDER BY decile;

-- Q47. Fastest-growing category (last month vs first month revenue).
WITH cat_month AS (
    SELECT d.product_category_english AS category,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN fact_orders o ON i.order_id = o.order_id
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2
),
edges AS (
    SELECT category,
           FIRST_VALUE(revenue) OVER (PARTITION BY category ORDER BY month) AS first_rev,
           LAST_VALUE(revenue)  OVER (PARTITION BY category ORDER BY month
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_rev
    FROM cat_month
)
SELECT DISTINCT category,
       ROUND(first_rev, 2) AS first_rev,
       ROUND(last_rev, 2) AS last_rev,
       ROUND(100.0 * (last_rev - first_rev) / NULLIF(first_rev, 0), 1) AS growth_pct
FROM edges
WHERE first_rev > 0
ORDER BY growth_pct DESC
LIMIT 15;
