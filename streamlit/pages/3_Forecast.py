"""Forecast page: project monthly revenue forward.

Uses Holt-Winters exponential smoothing (statsmodels) when enough history is
available, otherwise falls back to a moving-average projection so the page
always renders. Purely illustrative — see ``notebooks/`` for model validation.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data as d

st.set_page_config(page_title="Forecast", page_icon="🔮", layout="wide")
st.title("🔮 Revenue Forecast")

try:
    mr = d.monthly_revenue()
except FileNotFoundError as exc:
    st.error(str(exc))
    st.stop()

if mr.empty:
    st.warning("No revenue history available.")
    st.stop()

horizon = st.slider("Forecast horizon (months)", 1, 12, 3)
series = mr.set_index("period")["revenue"].astype(float)


def _forecast(values: pd.Series, steps: int) -> pd.Series:
    if len(values) >= 6:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            model = ExponentialSmoothing(values, trend="add", seasonal=None).fit()
            return model.forecast(steps)
        except Exception:  # pragma: no cover - fallback path
            pass
    # Moving-average fallback
    window = min(3, len(values))
    avg = values.tail(window).mean()
    idx = [f"f+{i+1}" for i in range(steps)]
    return pd.Series([avg] * steps, index=idx)


fc = _forecast(series, horizon)

fig = go.Figure()
fig.add_trace(go.Scatter(x=series.index, y=series.values, name="Actual", mode="lines+markers"))
fig.add_trace(go.Scatter(x=list(fc.index), y=list(fc.values), name="Forecast",
                         mode="lines+markers", line=dict(dash="dash")))
fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Forecast values")
st.dataframe(
    fc.round(2).rename("forecast_revenue").rename_axis("period").reset_index(),
    use_container_width=True,
    hide_index=True,
)
st.info("Model: Holt-Winters (≥6 months of history) with a moving-average fallback.")
