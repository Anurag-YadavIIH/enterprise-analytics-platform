-- One row per order with typed timestamps and derived delivery metrics.
with source as (
    select * from {{ source('raw', 'orders') }}
)
select
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    date_diff('day', order_purchase_timestamp, order_delivered_customer_date) as delivery_days,
    date_diff('day', order_delivered_customer_date, order_estimated_delivery_date) as delivery_vs_estimate_days
from source
