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
raw_series = mr.set_index("period")["revenue"].astype(float)


def _drop_incomplete_tail(values: pd.Series, min_history: int = 4) -> pd.Series:
    """Drop trailing months that look like incomplete data collection.

    The real Olist dataset's final ~2 months have sharply reduced order
    volume because data collection stopped mid-month, not because demand
    collapsed. Left in, a linear-trend model reads that as a real cliff and
    extrapolates it into deeply negative forecasts. Heuristic: repeatedly
    drop the last month while its revenue is under 30% of the prior
    3-month average — a drop that severe is far more likely a
    data-completeness artifact than genuine demand collapse. Stops once
    ``min_history`` months remain so the fit never starves.
    """
    cleaned = values.copy()
    while len(cleaned) > min_history:
        prior_avg = cleaned.iloc[-4:-1].mean()
        if prior_avg > 0 and cleaned.iloc[-1] < 0.3 * prior_avg:
            cleaned = cleaned.iloc[:-1]
        else:
            break
    return cleaned


series = _drop_incomplete_tail(raw_series)
dropped = len(raw_series) - len(series)


def _forecast(values: pd.Series, steps: int) -> pd.Series:
    """Forecast ``steps`` months forward, always indexed by real YYYY-MM labels."""
    raw: pd.Series | None = None
    if len(values) >= 6:
        try:
            from statsmodels.tsa.holtwinters import ExponentialSmoothing

            model = ExponentialSmoothing(values, trend="add", seasonal=None).fit()
            raw = model.forecast(steps)
        except Exception:  # pragma: no cover - fallback path
            raw = None

    if raw is None:
        # Moving-average fallback.
        window = min(3, len(values))
        raw = pd.Series([values.tail(window).mean()] * steps)

    last_period = pd.Period(values.index[-1], freq="M")
    raw = raw.reset_index(drop=True)
    raw.index = [str(last_period + i) for i in range(1, steps + 1)]

    # Revenue can't be negative. This is a guardrail against model
    # overshoot, not the fix for the negative-forecast issue — the real fix
    # is excluding the incomplete tail months above before fitting.
    return raw.clip(lower=0)


fc = _forecast(series, horizon)

fig = go.Figure()
fig.add_trace(go.Scatter(x=raw_series.index, y=raw_series.values, name="Actual", mode="lines+markers"))
fig.add_trace(go.Scatter(x=list(fc.index), y=list(fc.values), name="Forecast",
                         mode="lines+markers", line=dict(dash="dash")))
fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, use_container_width=True)

if dropped:
    st.caption(
        f"Note: the last {dropped} month(s) of history are excluded from the forecast "
        "fit — data collection for this dataset tapers off sharply right at the end, "
        "which would otherwise be mistaken for a demand collapse and skew the trend."
    )

st.subheader("Forecast values")
st.dataframe(
    fc.round(2).rename("forecast_revenue").rename_axis("period").reset_index(),
    use_container_width=True,
    hide_index=True,
)
st.info("Model: Holt-Winters (≥6 months of history) with a moving-average fallback.")
st.caption(
    "This is a naive time-series projection fit on 2016-2018 historical data for "
    "demonstration purposes, not a production-grade forecast — it models trend only, "
    "with no seasonality, marketing calendar, or macro conditions."
)
