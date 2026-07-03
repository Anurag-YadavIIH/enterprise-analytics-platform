"""Insights page: actionable, quantified recommendations from Olist's own data.

Every figure on this page is computed live from the DuckDB warehouse (see the
matching queries in sql/queries/08_insights.sql). This is Olist's own
2016-2018 transaction data -- there is no competitor data and no external
market data here. Where a recommendation would need that, it says so instead
of inventing a number.
"""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data as d

st.set_page_config(page_title="Insights", page_icon="💡", layout="wide")
st.title("💡 Actionable Insights")
st.caption(
    "Every number below is computed from Olist's own 2016-2018 transaction data. "
    "There is no competitor or external market data in this warehouse -- where a "
    "recommendation would need that, it's called out explicitly rather than guessed at."
)

try:
    aov = d.avg_order_value()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# 1. Delivery impact on retention
# ---------------------------------------------------------------------------
st.header("1. Does a late first delivery cost us repeat customers?")

dr = d.delivery_retention()
late_by_state = d.late_delivery_by_state()
on_time = dr[dr["first_delivery_status"] == "on_time"].iloc[0]
late = dr[dr["first_delivery_status"] == "late"].iloc[0]

c1, c2 = st.columns([1, 1])
with c1:
    fig = px.bar(
        dr, x="first_delivery_status", y="repeat_rate_pct", color="first_delivery_status",
        labels={"first_delivery_status": "First order delivery", "repeat_rate_pct": "Repeat-purchase rate (%)"},
        color_discrete_map={"on_time": "#1f77b4", "late": "#d62728"},
    )
    fig.update_layout(height=340, margin={"l": 0, "r": 0, "t": 10, "b": 0}, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
with c2:
    st.dataframe(dr, use_container_width=True, hide_index=True)

repeat_gap_pp = on_time["repeat_rate_pct"] - late["repeat_rate_pct"]
missed_repeat_customers = late["customers"] * repeat_gap_pp / 100
revenue_at_risk = missed_repeat_customers * aov
top_states = ", ".join(late_by_state.head(5)["customer_state"])

st.info(
    f"**So what?** Customers whose first order arrived late repeat-purchase at "
    f"{late['repeat_rate_pct']:.2f}% vs {on_time['repeat_rate_pct']:.2f}% for on-time "
    f"customers -- a {repeat_gap_pp:.2f}-point gap. Applied to the "
    f"{late['customers']:,} customers whose first delivery was late, that's roughly "
    f"**{missed_repeat_customers:.0f} fewer repeat customers**, worth an estimated "
    f"**R\\$ {revenue_at_risk:,.0f}** in forgone revenue at the site-wide average order "
    f"value of R\\$ {aov:,.2f}.\n\n"
    f"Note: average LTV is actually *higher* for late-first-order customers "
    f"(R\\$ {late['avg_ltv']:,.2f} vs R\\$ {on_time['avg_ltv']:,.2f}) -- their first order tends "
    f"to be bigger. The retention hit shows up in whether they come back at all, not in "
    f"what they spend when they do.\n\n"
    f"**Recommendation:** prioritize delivery-reliability fixes in **{top_states}** -- "
    f"the states with the highest late-delivery rates "
    f"({late_by_state.iloc[0]['late_pct']:.1f}% in {late_by_state.iloc[0]['customer_state']} alone)."
)

with st.expander("Late-delivery rate by state (states with < 30 delivered orders excluded)"):
    fig2 = px.bar(
        late_by_state.head(15), x="customer_state", y="late_pct",
        labels={"customer_state": "State", "late_pct": "Late-delivery rate (%)"},
    )
    fig2.update_layout(height=360, margin={"l": 0, "r": 0, "t": 10, "b": 0})
    st.plotly_chart(fig2, use_container_width=True)
    st.dataframe(late_by_state, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Freight profitability
# ---------------------------------------------------------------------------
st.header("2. Where is freight eating margin?")

freight_cat = d.freight_by_category()
threshold = st.slider("Flag categories where freight exceeds this % of price", 10, 100, 40, step=5)
flagged = freight_cat[freight_cat["freight_pct_of_price"] > threshold]
margin_negative = freight_cat[freight_cat["freight_pct_of_price"] > 100]

fig = px.bar(
    freight_cat.head(15), x="freight_pct_of_price", y="category", orientation="h",
    labels={"freight_pct_of_price": "Freight as % of price", "category": "Category"},
)
fig.update_layout(height=460, margin={"l": 0, "r": 0, "t": 10, "b": 0}, yaxis={"categoryorder": "total ascending"})
st.plotly_chart(fig, use_container_width=True)

if margin_negative.empty:
    margin_note = "No category is margin-negative on freight on average -- freight never exceeds price."
else:
    names = ", ".join(margin_negative["category"])
    margin_note = f"{len(margin_negative)} categories ARE margin-negative on freight: {names}."

st.info(
    f"**So what?** At a {threshold}% threshold, **{len(flagged)} categories** carry freight "
    f"above that share of price, led by **{freight_cat.iloc[0]['category']}** at "
    f"{freight_cat.iloc[0]['freight_pct_of_price']:.1f}% (avg price R\\$ {freight_cat.iloc[0]['avg_price']:.2f}, "
    f"avg freight R\\$ {freight_cat.iloc[0]['avg_freight']:.2f}). {margin_note}\n\n"
    f"**Recommendation:** for categories above the threshold, either fold freight into the "
    f"listed price (one number, no checkout surprise) or investigate the specific "
    f"category/region combinations below for a targeted carrier-rate renegotiation."
)

with st.expander("Freight burden by category x state (worst combinations, min. 20 items per cell)"):
    fbcr = d.freight_by_category_region()
    st.dataframe(fbcr.head(30), use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# 3. RFM win-back action list
# ---------------------------------------------------------------------------
st.header("3. Who should we win back this month?")
st.caption('Segment definitions match sql/queries/06_rfm_and_segmentation.sql (Q60).')

winback = d.rfm_winback_list()
segment_filter = st.multiselect(
    "Segment", options=["At Risk", "Cannot Lose Them"], default=["At Risk", "Cannot Lose Them"]
)
filtered = winback[winback["segment"].isin(segment_filter)]

c1, c2 = st.columns(2)
c1.metric("Customers targeted", f"{len(filtered):,}")
c2.metric("Revenue represented", f"R$ {filtered['monetary'].sum():,.0f}")

st.dataframe(filtered, use_container_width=True, hide_index=True, height=300)
st.download_button(
    "Download win-back list (CSV)", filtered.to_csv(index=False), "winback_list.csv", "text/csv"
)

st.info(
    f"**So what?** {len(filtered):,} customers across {' and '.join(segment_filter) or 'no segments'} "
    f"represent **R\\$ {filtered['monetary'].sum():,.0f}** in historical revenue that's gone quiet.\n\n"
    f"**Recommendation:** target this exact list with a win-back campaign this month -- it's "
    f"a known, high-value audience (identified from actual past spend) rather than a cold list."
)

st.divider()

# ---------------------------------------------------------------------------
# 4. Cohort payback
# ---------------------------------------------------------------------------
st.header("4. How long does a customer cohort take to mature?")

payback = d.payback_curve()
max_available = int(payback["months_since_first_order"].max())
max_month = st.slider("Months to show", 3, max_available, min(12, max_available))
view = payback[payback["months_since_first_order"] <= max_month]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=view["months_since_first_order"], y=view["cumulative_revenue_per_customer"],
    mode="lines+markers", name="Cumulative revenue / customer",
))
fig.update_layout(
    height=380, margin={"l": 0, "r": 0, "t": 10, "b": 0},
    xaxis_title="Months since first order", yaxis_title="Cumulative R$ / customer",
)
st.plotly_chart(fig, use_container_width=True)

month0 = payback[payback["months_since_first_order"] == 0].iloc[0]
final = view.iloc[-1]
pct_in_month0 = 100 * month0["cumulative_revenue_per_customer"] / final["cumulative_revenue_per_customer"]

st.info(
    f"**So what?** {pct_in_month0:.1f}% of the cumulative revenue a customer generates through "
    f"month {int(final['months_since_first_order'])} arrives in their very first purchase month. "
    f"Cumulative revenue per customer only grows from R\\$ {month0['cumulative_revenue_per_customer']:.2f} "
    f"at month 0 to R\\$ {final['cumulative_revenue_per_customer']:.2f} by month "
    f"{int(final['months_since_first_order'])}.\n\n"
    f"**In plain language:** cohorts don't really \"mature\" on this platform -- almost all "
    f"the value from a customer is captured (or lost) at their first purchase, which lines up "
    f"with the roughly 3% repeat-purchase rate seen in Insight 1.\n\n"
    f"**Recommendation:** retention spend is better aimed at converting the *first* purchase "
    f"into a second one quickly (e.g. a timed post-purchase offer) than at long-horizon "
    f"loyalty programs -- there's little cohort revenue left to protect after month 0."
)

st.divider()

# ---------------------------------------------------------------------------
# 5. Geographic opportunity
# ---------------------------------------------------------------------------
st.header("5. Which states are high-value but underserved?")

geo = d.geo_opportunity()
fig = px.scatter(
    geo, x="avg_delivery_days", y="revenue_per_customer", size="customers", text="customer_state",
    labels={"avg_delivery_days": "Avg delivery days", "revenue_per_customer": "Revenue per customer (R$)"},
)
fig.update_traces(textposition="top center")
fig.update_layout(height=460, margin={"l": 0, "r": 0, "t": 10, "b": 0})
st.plotly_chart(fig, use_container_width=True)

median_delivery = geo["avg_delivery_days"].median()
median_revenue = geo["revenue_per_customer"].median()
opportunity = geo[
    (geo["revenue_per_customer"] > median_revenue) & (geo["avg_delivery_days"] > median_delivery)
].sort_values("revenue_per_customer", ascending=False)

if opportunity.empty:
    opp_note = "No state currently sits in the high-value / slow-delivery quadrant."
else:
    top = opportunity.iloc[0]
    states = ", ".join(opportunity["customer_state"].head(5))
    opp_note = (
        f"**{states}** sit in the high-value, slow-delivery quadrant (above the median on both "
        f"revenue per customer and delivery days). **{top['customer_state']}** stands out most: "
        f"R\\$ {top['revenue_per_customer']:.2f} revenue per customer despite a "
        f"{top['avg_delivery_days']:.1f}-day average delivery."
    )

st.info(
    f"**So what?** {opp_note}\n\n"
    f"**Recommendation:** these states justify logistics investment (regional fulfillment "
    f"partners, carrier renegotiation) ahead of lower-value states with similarly slow "
    f"delivery -- the revenue upside is already proven; delivery speed is the constraint."
)
