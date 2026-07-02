-- Product dimension (with English categories).
select * from {{ ref('stg_products') }}
