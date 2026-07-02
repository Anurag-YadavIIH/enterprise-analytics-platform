-- Category-level performance mart.
select
    p.product_category_english as category,
    count(distinct i.order_id) as orders,
    round(sum(i.price), 2)     as revenue,
    round(avg(i.price), 2)     as avg_item_price,
    round(sum(i.freight_value), 2) as freight
from {{ ref('stg_order_items') }} i
left join {{ ref('dim_products') }} p on i.product_id = p.product_id
group by 1
