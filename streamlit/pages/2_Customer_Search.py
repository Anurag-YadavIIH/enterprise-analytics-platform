"""Customer search page with state filter and minimum-spend slider."""

from __future__ import annotations

import streamlit as st

import data as d

st.set_page_config(page_title="Customer Search", page_icon="🔎", layout="wide")
st.title("🔎 Customer Search")

try:
    state_options = ["All", *d.states()]
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

col1, col2 = st.columns(2)
state = col1.selectbox("State", state_options)
min_spent = col2.slider("Minimum total spent (R$)", 0.0, 5000.0, 0.0, step=50.0)

results = d.search_customers(None if state == "All" else state, min_spent)
st.caption(f"{len(results):,} customers match")
st.dataframe(results, use_container_width=True, hide_index=True)

if not results.empty:
    st.download_button(
        "Download CSV",
        results.to_csv(index=False).encode("utf-8"),
        file_name="customers.csv",
        mime="text/csv",
    )
