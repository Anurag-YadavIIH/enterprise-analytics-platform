-- Review records with answer latency.
select
    review_id,
    order_id,
    review_score,
    review_creation_date,
    review_answer_timestamp,
    date_diff('day', review_creation_date, review_answer_timestamp) as answer_latency_days
from {{ source('raw', 'order_reviews') }}
