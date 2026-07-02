"""Olist Analytics — Streamlit overview page.

Run with: streamlit run streamlit/app.py
Multi-page: additional pages live in streamlit/pages/.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import data as d

st.set_page_config(page_title="Olist Analytics", page_icon="📦", layout="wide")

st.title("📦 Olist Enterprise Analytics")
st.caption("End-to-end retail analytics on the Olist Brazilian e-commerce dataset.")

try:
    k = d.kpis()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Orders", f"{k['total_orders']:,}")
c2.metric("Total Revenue", f"R$ {k['total_revenue']:,.0f}")
c3.metric("Avg Order Value", f"R$ {k['avg_order_value']:,.2f}")
c4.metric("Unique Customers", f"{k['unique_customers']:,}")
c5.metric("Avg Review", f"{k['avg_review']:.2f} ★")

st.divider()

left, right = st.columns(2)
with left:
    st.subheader("Monthly Revenue")
    mr = d.monthly_revenue()
    if not mr.empty:
        fig = px.line(mr, x="period", y="revenue", markers=True)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Revenue by State")
    rs = d.revenue_by_state().head(12)
    if not rs.empty:
        fig = px.bar(rs, x="state", y="revenue")
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=320)
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Top Categories by Revenue")
cat = d.category_revenue().head(15)
if not cat.empty:
    fig = px.bar(cat, x="revenue", y="category", orientation="h")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=420,
                      yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

st.caption("Use the sidebar to open Analytics, Customer Search and Forecast pages.")
