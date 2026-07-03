-- =====================================================================
-- SECTION 8 — Actionable insights (Q79–Q87)
-- Unlike sections 1-7, every query here is written to inform a specific
-- business decision, not just report a metric. Each is commented with the
-- question it answers AND the decision it's meant to inform. Powers the
-- Streamlit "Insights" page (streamlit/pages/4_Insights.py).
--
-- Schema: olist star schema (dim_*, fact_*). Runs on DuckDB & PostgreSQL.
-- All figures come from Olist's own 2016-2018 transaction data — there is
-- no competitor or external market data anywhere in this warehouse.
-- =====================================================================

-- Q79. Does a late first delivery change repeat-purchase behaviour and LTV?
-- Decision: quantifies the retention cost of a bad first-delivery experience,
-- to justify (or size) investment in on-time delivery for new customers.
WITH first_order AS (
    SELECT c.customer_unique_id,
           o.order_id,
           o.delivery_vs_estimate_days,
           ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                              ORDER BY o.order_purchase_timestamp) AS seq
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    WHERE o.order_delivered_customer_date IS NOT NULL
),
first_only AS (
    -- delivery_vs_estimate_days = estimated minus delivered, so negative means late.
    SELECT customer_unique_id,
           CASE WHEN delivery_vs_estimate_days < 0 THEN 'late' ELSE 'on_time' END AS first_delivery_status
    FROM first_order WHERE seq = 1
),
cust_stats AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT o.order_id) AS total_orders,
           SUM(p.payment_value) AS ltv
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
)
SELECT f.first_delivery_status,
       COUNT(*) AS customers,
       ROUND(100.0 * AVG(CASE WHEN cs.total_orders > 1 THEN 1 ELSE 0 END), 2) AS repeat_rate_pct,
       ROUND(AVG(cs.ltv), 2) AS avg_ltv
FROM first_only f
JOIN cust_stats cs ON f.customer_unique_id = cs.customer_unique_id
GROUP BY f.first_delivery_status;

-- Q80. Which states have the worst late-delivery rate?
-- Decision: prioritization list for logistics/carrier investment — states
-- with high order volume AND high late-rate are the highest-leverage fixes.
SELECT c.customer_state,
       COUNT(*) AS delivered_orders,
       COUNT(*) FILTER (WHERE o.delivery_vs_estimate_days < 0) AS late_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE o.delivery_vs_estimate_days < 0) / COUNT(*), 2) AS late_pct
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
WHERE o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
HAVING COUNT(*) >= 30  -- drop states with too few orders to be reliable
ORDER BY late_pct DESC;

-- Q81. Where is freight burden worst, by category AND region together?
-- Decision: surfaces category/region combinations for targeted fixes
-- (regional carrier renegotiation, or category-specific packaging/pricing)
-- rather than a one-size-fits-all national freight policy.
SELECT COALESCE(d.product_category_english, 'unknown') AS category,
       c.customer_state,
       COUNT(*) AS items,
       ROUND(AVG(i.price), 2) AS avg_price,
       ROUND(AVG(i.freight_value), 2) AS avg_freight,
       ROUND(100.0 * AVG(i.freight_value) / NULLIF(AVG(i.price), 0), 2) AS freight_pct_of_price
FROM fact_order_items i
JOIN fact_orders o ON i.order_id = o.order_id
JOIN dim_customers c ON o.customer_id = c.customer_id
LEFT JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1, 2
HAVING COUNT(*) >= 20  -- drop category/region cells too small to trust
ORDER BY freight_pct_of_price DESC;

-- Q82. Which product categories carry the heaviest freight burden nationally?
-- Decision: candidates for a pricing floor (freight-inclusive pricing) or a
-- packaging/logistics review — freight this large relative to price is a
-- likely reason for cart abandonment or thin margins on these categories.
SELECT COALESCE(d.product_category_english, 'unknown') AS category,
       COUNT(*) AS items,
       ROUND(AVG(i.price), 2) AS avg_price,
       ROUND(AVG(i.freight_value), 2) AS avg_freight,
       ROUND(100.0 * AVG(i.freight_value) / NULLIF(AVG(i.price), 0), 2) AS freight_pct_of_price
FROM fact_order_items i
LEFT JOIN dim_products d ON i.product_id = d.product_id
GROUP BY 1
HAVING COUNT(*) >= 20
ORDER BY freight_pct_of_price DESC;

-- Q83. Who are the "At Risk" and "Cannot Lose Them" customers, by name, for a
-- win-back campaign? (Segment definitions match Q60.)
-- Decision: a directly actionable, downloadable target list for a win-back
-- campaign this month, not just a segment count.
WITH ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders),
rfm AS (
    SELECT c.customer_unique_id,
           DATE_DIFF('day', MAX(o.order_purchase_timestamp), (SELECT max_ts FROM ref)) AS recency_days,
           COUNT(DISTINCT o.order_id) AS frequency,
           SUM(p.payment_value) AS monetary
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
),
scored AS (
    -- customer_unique_id is a deterministic tie-breaker: recency/frequency/monetary
    -- have heavy ties, and NTILE's tie handling is otherwise unstable across runs
    -- without a fully-ordered key — see sql/queries/06 Q59 for the same fix.
    SELECT customer_unique_id, recency_days, frequency, monetary,
           6 - NTILE(5) OVER (ORDER BY recency_days, customer_unique_id) AS r,
           NTILE(5) OVER (ORDER BY frequency, customer_unique_id)        AS f,
           NTILE(5) OVER (ORDER BY monetary, customer_unique_id)         AS m
    FROM rfm
),
segmented AS (
    SELECT *,
        CASE
            WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
            WHEN r >= 4 AND f >= 3            THEN 'Loyal'
            WHEN r >= 4 AND f <= 2            THEN 'New / Promising'
            WHEN r = 3                        THEN 'Needs Attention'
            WHEN r <= 2 AND f >= 4            THEN 'At Risk'
            WHEN r <= 2 AND m >= 4            THEN 'Cannot Lose Them'
            ELSE 'Hibernating'
        END AS segment
    FROM scored
)
SELECT customer_unique_id, segment, recency_days, frequency, ROUND(monetary, 2) AS monetary
FROM segmented
WHERE segment IN ('At Risk', 'Cannot Lose Them')
ORDER BY monetary DESC;

-- Q84. How much revenue do the "At Risk" + "Cannot Lose Them" segments
-- represent in total?
-- Decision: sizes the win-back campaign's opportunity — the number that
-- justifies the marketing spend on Q83's target list.
WITH ref AS (SELECT MAX(order_purchase_timestamp) AS max_ts FROM fact_orders),
rfm AS (
    SELECT c.customer_unique_id,
           DATE_DIFF('day', MAX(o.order_purchase_timestamp), (SELECT max_ts FROM ref)) AS recency_days,
           COUNT(DISTINCT o.order_id) AS frequency,
           SUM(p.payment_value) AS monetary
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY c.customer_unique_id
),
scored AS (
    -- customer_unique_id is a deterministic tie-breaker (see Q59 for why).
    SELECT customer_unique_id, monetary,
           6 - NTILE(5) OVER (ORDER BY recency_days, customer_unique_id) AS r,
           NTILE(5) OVER (ORDER BY frequency, customer_unique_id)        AS f,
           NTILE(5) OVER (ORDER BY monetary, customer_unique_id)         AS m
    FROM rfm
),
segmented AS (
    SELECT *,
        CASE
            WHEN r >= 4 AND f >= 4 AND m >= 4 THEN 'Champions'
            WHEN r >= 4 AND f >= 3            THEN 'Loyal'
            WHEN r >= 4 AND f <= 2            THEN 'New / Promising'
            WHEN r = 3                        THEN 'Needs Attention'
            WHEN r <= 2 AND f >= 4            THEN 'At Risk'
            WHEN r <= 2 AND m >= 4            THEN 'Cannot Lose Them'
            ELSE 'Hibernating'
        END AS segment
    FROM scored
)
SELECT segment, COUNT(*) AS customers, ROUND(SUM(monetary), 2) AS total_revenue
FROM segmented
WHERE segment IN ('At Risk', 'Cannot Lose Them')
GROUP BY segment
ORDER BY total_revenue DESC;

-- Q85. Cohort x months-since-acquisition revenue matrix.
-- Decision: raw material for a payback-period chart per cohort, so finance
-- can see whether newer cohorts are maturing faster or slower than older ones.
WITH first_order AS (
    SELECT c.customer_unique_id,
           MIN(DATE_TRUNC('month', o.order_purchase_timestamp)) AS cohort_month
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
order_rev AS (
    SELECT c.customer_unique_id,
           DATE_TRUNC('month', o.order_purchase_timestamp) AS order_month,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    GROUP BY 1, 2
)
SELECT f.cohort_month,
       DATE_DIFF('month', f.cohort_month, r.order_month) AS months_since_first_order,
       ROUND(SUM(r.revenue), 2) AS revenue
FROM first_order f
JOIN order_rev r ON f.customer_unique_id = r.customer_unique_id
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q86. Pooled payback curve: cumulative revenue per customer by months since
-- acquisition, averaged across all cohorts (smooths out single-cohort noise).
-- Decision: answers "how long does it take a cohort to mature?" in one
-- number a non-technical stakeholder can act on.
WITH first_order AS (
    SELECT c.customer_unique_id, MIN(o.order_purchase_timestamp) AS first_ts
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    GROUP BY c.customer_unique_id
),
cohort_size AS (SELECT COUNT(*) AS n_customers FROM first_order),
order_rev AS (
    SELECT c.customer_unique_id,
           DATE_DIFF('month', f.first_ts, o.order_purchase_timestamp) AS months_since_first_order,
           SUM(p.payment_value) AS revenue
    FROM fact_orders o
    JOIN dim_customers c ON o.customer_id = c.customer_id
    JOIN fact_payments p ON o.order_id = p.order_id
    JOIN first_order f ON c.customer_unique_id = f.customer_unique_id
    GROUP BY 1, 2
)
SELECT months_since_first_order,
       ROUND(SUM(revenue), 2) AS total_revenue,
       ROUND(SUM(revenue) / (SELECT n_customers FROM cohort_size), 2) AS revenue_per_customer,
       ROUND(SUM(SUM(revenue)) OVER (ORDER BY months_since_first_order)
             / (SELECT n_customers FROM cohort_size), 2) AS cumulative_revenue_per_customer
FROM order_rev
GROUP BY months_since_first_order
ORDER BY months_since_first_order;

-- Q87. Revenue-per-customer vs. average delivery days, by state.
-- Decision: surfaces "high-value but underserved" states — high spend per
-- customer combined with slow delivery is an expansion opportunity if
-- logistics investment can close the delivery gap.
SELECT c.customer_state,
       COUNT(DISTINCT c.customer_unique_id) AS customers,
       ROUND(SUM(p.payment_value) / COUNT(DISTINCT c.customer_unique_id), 2) AS revenue_per_customer,
       ROUND(AVG(o.delivery_days), 1) AS avg_delivery_days
FROM fact_orders o
JOIN dim_customers c ON o.customer_id = c.customer_id
JOIN fact_payments p ON o.order_id = p.order_id
WHERE o.delivery_days IS NOT NULL
GROUP BY c.customer_state
HAVING COUNT(DISTINCT c.customer_unique_id) >= 30
ORDER BY revenue_per_customer DESC;
