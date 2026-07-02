-- =====================================================================
-- SECTION 5 — Cohort & retention analysis (Q48–Q57)
-- Acquisition cohorts, month-N retention, repeat-purchase behaviour.
-- =====================================================================

-- Q48. Assign each customer to an acquisition cohort (first-purchase month).
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(DATE_TRUNC('month', o.order_purchase_timestamp)) AS cohort_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
)
SELECT cohort_month, COUNT(*) AS new_customers
FROM first_order
GROUP BY cohort_month
ORDER BY cohort_month;

-- Q49. Cohort retention matrix: customers active N months after acquisition.
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(DATE_TRUNC('month', o.order_purchase_timestamp)) AS cohort_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
activity AS (
    SELECT c.customer_unique_id,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS active_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY 1, 2
)
SELECT f.cohort_month,
       DATE_DIFF('month', f.cohort_month, a.active_month) AS month_offset,
       COUNT(DISTINCT a.customer_unique_id) AS active_customers
FROM first_order f
JOIN activity a ON f.customer_unique_id = a.customer_unique_id
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q50. Month-1 retention rate per cohort.
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(DATE_TRUNC('month', o.order_purchase_timestamp)) AS cohort_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
activity AS (
    SELECT c.customer_unique_id,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS active_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY 1, 2
),
offsets AS (
    SELECT f.cohort_month, f.customer_unique_id,
           DATE_DIFF('month', f.cohort_month, a.active_month) AS mo
    FROM first_order f
    JOIN activity a ON f.customer_unique_id = a.customer_unique_id
)
SELECT cohort_month,
       COUNT(DISTINCT CASE WHEN mo = 0 THEN customer_unique_id END) AS cohort_size,
       COUNT(DISTINCT CASE WHEN mo = 1 THEN customer_unique_id END) AS retained_m1,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN mo = 1 THEN customer_unique_id END)
             / NULLIF(COUNT(DISTINCT CASE WHEN mo = 0 THEN customer_unique_id END), 0), 2) AS m1_retention_pct
FROM offsets
GROUP BY cohort_month
ORDER BY cohort_month;

-- Q51. Repeat-purchase rate (share of customers with >1 order).
SELECT ROUND(100.0 * AVG(CASE WHEN n_orders > 1 THEN 1 ELSE 0 END), 2) AS repeat_rate_pct
FROM (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS n_orders
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
) t;

-- Q52. Time between first and second purchase (days) distribution.
WITH ranked AS (
    SELECT c.customer_unique_id, o.order_purchase_timestamp,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp) AS seq
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
),
first_second AS (
    SELECT customer_unique_id,
           MAX(CASE WHEN seq = 1 THEN order_purchase_timestamp END) AS first_p,
           MAX(CASE WHEN seq = 2 THEN order_purchase_timestamp END) AS second_p
    FROM ranked WHERE seq <= 2 GROUP BY customer_unique_id
)
SELECT ROUND(AVG(DATE_DIFF('day', first_p, second_p)), 1) AS avg_days_to_second,
       MIN(DATE_DIFF('day', first_p, second_p)) AS min_days,
       MAX(DATE_DIFF('day', first_p, second_p)) AS max_days
FROM first_second
WHERE second_p IS NOT NULL;

-- Q53. Monthly active customers (MAC) trend.
SELECT DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
       COUNT(DISTINCT c.customer_unique_id) AS active_customers
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
GROUP BY 1
ORDER BY 1;

-- Q54. New vs returning revenue split by month.
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(DATE_TRUNC('month', o.order_purchase_timestamp)) AS cohort_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
order_rev AS (
    SELECT c.customer_unique_id,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS month,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY 1, 2
)
SELECT r.month,
       ROUND(SUM(CASE WHEN r.month = f.cohort_month THEN r.revenue ELSE 0 END), 2) AS new_revenue,
       ROUND(SUM(CASE WHEN r.month > f.cohort_month THEN r.revenue ELSE 0 END), 2) AS returning_revenue
FROM order_rev r
JOIN first_order f ON r.customer_unique_id = f.customer_unique_id
GROUP BY r.month
ORDER BY r.month;

-- Q55. Churn proxy: customers with no order in the last 180 days of data.
WITH last_order AS (
    SELECT c.customer_unique_id,
           MAX(o.order_purchase_timestamp) AS last_ts
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders)
SELECT COUNT(*) FILTER (WHERE DATE_DIFF('day', last_ts, max_ts) > 180) AS churned,
       COUNT(*) AS total,
       ROUND(100.0 * COUNT(*) FILTER (WHERE DATE_DIFF('day', last_ts, max_ts) > 180)
             / COUNT(*), 2) AS churn_pct
FROM last_order CROSS JOIN ref;

-- Q56. Cohort revenue: total revenue generated by each acquisition cohort.
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(DATE_TRUNC('month', o.order_purchase_timestamp)) AS cohort_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
cust_rev AS (
    SELECT c.customer_unique_id, SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT f.cohort_month,
       COUNT(*) AS customers,
       ROUND(SUM(cr.revenue), 2) AS cohort_revenue,
       ROUND(AVG(cr.revenue), 2) AS avg_ltv
FROM first_order f
JOIN cust_rev cr ON f.customer_unique_id = cr.customer_unique_id
GROUP BY f.cohort_month
ORDER BY f.cohort_month;

-- Q57. Average orders per customer within first 90 days of acquisition.
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(o.order_purchase_timestamp) AS first_ts
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
early AS (
    SELECT c.customer_unique_id,
           COUNT(*) FILTER (
               WHERE DATE_DIFF('day', f.first_ts, o.order_purchase_timestamp) <= 90
           ) AS orders_90d
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN first_order f ON c.customer_unique_id = f.customer_unique_id
    GROUP BY c.customer_unique_id
)
SELECT ROUND(AVG(orders_90d), 3) AS avg_orders_first_90d FROM early;
