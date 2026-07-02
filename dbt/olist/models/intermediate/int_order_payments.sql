-- Aggregate payments to one row per order.
select
    order_id,
    sum(payment_value)        as payment_value,
    max(payment_installments) as max_installments,
    count(*)                  as payment_count
from {{ ref('stg_order_payments') }}
group by order_id
