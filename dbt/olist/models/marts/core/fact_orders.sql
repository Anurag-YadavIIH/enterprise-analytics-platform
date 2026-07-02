-- Wide order fact: one row per order joined to payments, items and reviews.
with o as (select * from {{ ref('stg_orders') }}),
pay as (select * from {{ ref('int_order_payments') }}),
items as (select * from {{ ref('int_order_items_agg') }}),
rev as (select * from {{ ref('int_order_reviews') }})
select
    o.order_id,
    o.customer_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.delivery_days,
    o.delivery_vs_estimate_days,
    items.item_count,
    items.distinct_products,
    items.items_value,
    items.freight_value,
    pay.payment_value,
    pay.max_installments,
    rev.review_score
from o
left join pay   on o.order_id = pay.order_id
left join items on o.order_id = items.order_id
left join rev   on o.order_id = rev.order_id
