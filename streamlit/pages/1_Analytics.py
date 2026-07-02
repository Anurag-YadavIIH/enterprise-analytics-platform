"""Analytics page: category and geography deep-dive with filters."""

from __future__ import annotations

import plotly.express as px
import streamlit as st

import data as d

st.set_page_config(page_title="Analytics", page_icon="📊", layout="wide")
st.title("📊 Analytics")

try:
    cats = d.category_revenue()
    geo = d.revenue_by_state()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

top_n = st.slider("Top N categories", 5, 30, 15)
metric = st.radio("Metric", ["revenue", "orders"], horizontal=True)

st.subheader(f"Top {top_n} categories by {metric}")
view = cats.sort_values(metric, ascending=False).head(top_n)
fig = px.bar(view, x=metric, y="category", orientation="h")
fig.update_layout(height=520, yaxis={"categoryorder": "total ascending"},
                  margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Geographic distribution")
st.dataframe(geo, use_container_width=True, hide_index=True)
