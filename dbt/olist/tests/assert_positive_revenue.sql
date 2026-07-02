-- Singular test: monthly revenue must never be negative.
select order_month, revenue
from {{ ref('fct_monthly_revenue') }}
where revenue < 0
