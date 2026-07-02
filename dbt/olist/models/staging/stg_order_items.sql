-- Order line items with total value per line.
with source as (
    select * from {{ source('raw', 'order_items') }}
)
select
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value,
    price + freight_value as total_item_value
from source
