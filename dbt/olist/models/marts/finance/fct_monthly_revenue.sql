-- Monthly delivered revenue KPI mart.
select
    date_trunc('month', order_purchase_timestamp) as order_month,
    count(distinct order_id) as orders,
    round(sum(payment_value), 2) as revenue,
    round(avg(payment_value), 2) as avg_order_value
from {{ ref('fact_orders') }}
where order_status = 'delivered'
group by 1
