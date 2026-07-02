-- Products enriched with English category names.
with p as (
    select * from {{ source('raw', 'products') }}
),
t as (
    select * from {{ source('raw', 'product_category_translation') }}
)
select
    p.product_id,
    p.product_category_name,
    coalesce(t.product_category_name_english, p.product_category_name) as product_category_english,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    p.product_photos_qty
from p
left join t on p.product_category_name = t.product_category_name
