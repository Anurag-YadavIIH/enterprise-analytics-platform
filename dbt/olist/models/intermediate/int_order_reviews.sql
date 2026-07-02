-- Average review score per order (orders may have multiple reviews).
select
    order_id,
    avg(review_score)        as review_score,
    max(answer_latency_days) as answer_latency_days
from {{ ref('stg_order_reviews') }}
group by order_id
