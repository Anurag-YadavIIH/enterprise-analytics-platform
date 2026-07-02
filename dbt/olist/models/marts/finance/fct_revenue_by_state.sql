-- Revenue and orders by customer state.
select
    c.customer_state,
    count(distinct f.order_id) as orders,
    round(sum(f.payment_value), 2) as revenue
from {{ ref('fact_orders') }} f
join {{ ref('dim_customers') }} c on f.customer_id = c.customer_id
group by 1
