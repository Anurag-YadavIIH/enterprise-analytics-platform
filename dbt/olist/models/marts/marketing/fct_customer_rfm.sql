-- Customer-level RFM metrics and quintile scores.
with ref as (
    select max(order_purchase_timestamp) as max_ts from {{ ref('fact_orders') }}
),
base as (
    select
        c.customer_unique_id,
        date_diff('day', max(f.order_purchase_timestamp), (select max_ts from ref)) as recency_days,
        count(distinct f.order_id) as frequency,
        sum(f.payment_value) as monetary
    from {{ ref('fact_orders') }} f
    join {{ ref('dim_customers') }} c on f.customer_id = c.customer_id
    group by c.customer_unique_id
)
select
    customer_unique_id,
    recency_days,
    frequency,
    round(monetary, 2) as monetary,
    6 - ntile(5) over (order by recency_days) as r_score,
    ntile(5) over (order by frequency)        as f_score,
    ntile(5) over (order by monetary)         as m_score
from base
