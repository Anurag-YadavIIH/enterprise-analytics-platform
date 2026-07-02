-- Aggregate line items to one row per order.
select
    order_id,
    count(*)                     as item_count,
    count(distinct product_id)   as distinct_products,
    sum(price)                   as items_value,
    sum(freight_value)           as freight_value
from {{ ref('stg_order_items') }}
group by order_id
