-- =====================================================================
-- SECTION 2 — Window functions (Q13–Q27)
-- ROW_NUMBER, RANK, DENSE_RANK, LAG/LEAD, running totals, moving avgs,
-- NTILE, PERCENT_RANK, FIRST_VALUE/LAST_VALUE.
-- =====================================================================

-- Q13. Running (cumulative) monthly revenue.
WITH monthly AS (
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN fact_payments p ON o.order_id = p.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(SUM(revenue) OVER (ORDER BY month), 2) AS cumulative_revenue
FROM monthly
ORDER BY month;

-- Q14. Month-over-month revenue growth using LAG.
WITH monthly AS (
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN fact_payments p ON o.order_id = p.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(revenue - LAG(revenue) OVER (ORDER BY month), 2) AS mom_change,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
             / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS mom_pct
FROM monthly
ORDER BY month;

-- Q15. 3-month moving average of revenue.
WITH monthly AS (
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY 1
)
SELECT month,
       ROUND(revenue, 2) AS revenue,
       ROUND(AVG(revenue) OVER (ORDER BY month
             ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS moving_avg_3m
FROM monthly
ORDER BY month;

-- Q16. Rank customers by total spend (ROW_NUMBER vs RANK vs DENSE_RANK).
WITH spend AS (
    SELECT c.customer_unique_id,
           SUM(p.payment_value) AS total_spent
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT customer_unique_id,
       ROUND(total_spent, 2) AS total_spent,
       ROW_NUMBER() OVER (ORDER BY total_spent DESC) AS row_num,
       RANK()       OVER (ORDER BY total_spent DESC) AS rnk,
       DENSE_RANK() OVER (ORDER BY total_spent DESC) AS dense_rnk
FROM spend
ORDER BY total_spent DESC
LIMIT 20;

-- Q17. Top 3 products by revenue within each category (partitioned ranking).
WITH prod AS (
    SELECT d.product_category_english AS category,
           i.product_id,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2
)
SELECT category, product_id, ROUND(revenue, 2) AS revenue, rn
FROM (
    SELECT category, product_id, revenue,
           ROW_NUMBER() OVER (PARTITION BY category ORDER BY revenue DESC) AS rn
    FROM prod
) t
WHERE rn <= 3
ORDER BY category, rn;

-- Q18. Revenue percentile of each state (PERCENT_RANK).
WITH state_rev AS (
    SELECT c.customer_state, SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_state
)
SELECT customer_state,
       ROUND(revenue, 2) AS revenue,
       ROUND(PERCENT_RANK() OVER (ORDER BY revenue), 3) AS pct_rank
FROM state_rev
ORDER BY revenue DESC;

-- Q19. Quartile buckets of customers by spend (NTILE).
WITH spend AS (
    SELECT c.customer_unique_id, SUM(p.payment_value) AS total_spent
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT quartile,
       COUNT(*) AS customers,
       ROUND(MIN(total_spent), 2) AS min_spent,
       ROUND(MAX(total_spent), 2) AS max_spent,
       ROUND(AVG(total_spent), 2) AS avg_spent
FROM (
    SELECT total_spent, NTILE(4) OVER (ORDER BY total_spent) AS quartile
    FROM spend
) q
GROUP BY quartile
ORDER BY quartile;

-- Q20. First and most recent order date per customer (FIRST_VALUE/LAST_VALUE).
SELECT DISTINCT c.customer_unique_id,
       FIRST_VALUE(o.order_purchase_timestamp) OVER w AS first_order,
       LAST_VALUE(o.order_purchase_timestamp)  OVER w AS last_order
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WINDOW w AS (
    PARTITION BY c.customer_unique_id
    ORDER BY o.order_purchase_timestamp
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
)
LIMIT 20;

-- Q21. Share of category revenue within its month (ratio to partition total).
WITH cat_month AS (
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           d.product_category_english AS category,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN fact_orders o ON i.order_id = o.order_id
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2
)
SELECT month, category, ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * revenue / SUM(revenue) OVER (PARTITION BY month), 2) AS pct_of_month
FROM cat_month
ORDER BY month, revenue DESC;

-- Q22. Days since previous order per customer (LAG on timestamp).
SELECT customer_unique_id, order_id, order_purchase_timestamp,
       order_purchase_timestamp
         - LAG(order_purchase_timestamp) OVER (PARTITION BY customer_unique_id
                                               ORDER BY order_purchase_timestamp) AS gap
FROM (
    SELECT c.customer_unique_id, o.order_id, o.order_purchase_timestamp
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
) t
ORDER BY customer_unique_id, order_purchase_timestamp
LIMIT 30;

-- Q23. Cumulative distribution of order values (CUME_DIST).
SELECT order_id, ROUND(order_value, 2) AS order_value,
       ROUND(CUME_DIST() OVER (ORDER BY order_value), 4) AS cume_dist
FROM (
    SELECT order_id, SUM(payment_value) AS order_value
    FROM fact_payments GROUP BY order_id
) t
ORDER BY order_value DESC
LIMIT 25;

-- Q24. Best-selling product per state (ranked within partition).
WITH sp AS (
    SELECT c.customer_state AS state, i.product_id,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN fact_orders o ON i.order_id = o.order_id
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY 1, 2
)
SELECT state, product_id, ROUND(revenue, 2) AS revenue
FROM (
    SELECT state, product_id, revenue,
           RANK() OVER (PARTITION BY state ORDER BY revenue DESC) AS rnk
    FROM sp
) t
WHERE rnk = 1
ORDER BY revenue DESC;

-- Q25. Revenue vs. running category maximum (MAX window).
WITH monthly_cat AS (
    SELECT d.product_category_english AS category,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN fact_orders o ON i.order_id = o.order_id
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2
)
SELECT category, month, ROUND(revenue, 2) AS revenue,
       ROUND(MAX(revenue) OVER (PARTITION BY category ORDER BY month), 2) AS running_peak
FROM monthly_cat
ORDER BY category, month
LIMIT 50;

-- Q26. Difference between each order value and the customer's average.
WITH cust_orders AS (
    SELECT c.customer_unique_id, o.order_id,
           SUM(p.payment_value) AS order_value
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY 1, 2
)
SELECT customer_unique_id, order_id, ROUND(order_value, 2) AS order_value,
       ROUND(order_value - AVG(order_value)
             OVER (PARTITION BY customer_unique_id), 2) AS diff_from_avg
FROM cust_orders
ORDER BY customer_unique_id
LIMIT 30;

-- Q27. Dense-ranked category leaderboard by month.
WITH cat_month AS (
    SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           d.product_category_english AS category,
           SUM(i.price) AS revenue
    FROM fact_order_items i
    JOIN fact_orders o ON i.order_id = o.order_id
    JOIN dim_products d ON i.product_id = d.product_id
    GROUP BY 1, 2
)
SELECT month, category, ROUND(revenue, 2) AS revenue,
       DENSE_RANK() OVER (PARTITION BY month ORDER BY revenue DESC) AS rank_in_month
FROM cat_month
ORDER BY month, rank_in_month
LIMIT 50;
