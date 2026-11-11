"""Sales Intelligence Dashboard — Streamlit application.

Run:  streamlit run app.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sales_ai.ai import (
    PROVIDERS,
    ai_summary,
    answer_question,
    build_facts,
    context_tables,
    detect_anomalies,
    forecast_revenue,
    money,
    stream_answer_question,
    verify_api_key,
)
from sales_ai.cleaning import clean_superstore, looks_like_superstore, read_csv_flexible
from sales_ai.data import REQUIRED_COLUMNS, generate_sales_data, validate_sales_data

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sales Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Minimal global style — keep it subtle, no loud overrides
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Tighten metric cards */
    [data-testid="stMetricValue"] { font-size: 1.4rem; }
    [data-testid="stMetricDelta"] { font-size: 0.85rem; }
    /* Sidebar section spacing */
    section[data-testid="stSidebar"] .block-container { padding-top: 1.2rem; }
    /* Slightly muted captions */
    .stCaption { color: #6b7280; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def totals(d: pd.DataFrame) -> dict:
    rev = d["revenue"].sum()
    profit = d["profit"].sum()
    n = d["order_id"].nunique()
    return {
        "revenue": rev,
        "profit": profit,
        "orders": n,
        "margin": profit / rev * 100 if rev else 0.0,
        "aov": rev / n if n else 0.0,
    }


def delta_pct(cur: float, prev: float):
    return None if not prev else f"{(cur / prev - 1) * 100:+.1f}%"


def fmt(x: float, currency: str) -> str:
    return money(x, currency)


@st.cache_data(show_spinner="Generating sample data…")
def load_sample() -> pd.DataFrame:
    return generate_sales_data()


@st.cache_data(show_spinner="Cleaning data…")
def load_superstore(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return clean_superstore(read_csv_flexible(path))


@st.cache_data(show_spinner=False)
def cached_forecast(df: pd.DataFrame, horizon: int):
    return forecast_revenue(df, horizon)


@st.cache_data(show_spinner=False)
def cached_anomalies(df: pd.DataFrame, contamination: float):
    return detect_anomalies(df, contamination)


@st.cache_data(show_spinner=False)
def cached_qa_context(df: pd.DataFrame, question: str) -> str:
    """Reuse compact aggregates while the data selection and question are unchanged."""
    return context_tables(df, question)


def get_env_key(name: str) -> str:
    """Read a key from Streamlit secrets or environment variables."""
    try:
        val = st.secrets.get(name)
    except Exception:
        val = None
    return val or os.getenv(name) or ""


# ---------------------------------------------------------------------------
# Sidebar — data source
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📊 Sales Intelligence")
    st.divider()

    st.markdown("**Data source**")
    source = st.radio(
        "Data source",
        ["Generated sample (₹)", "Superstore CSV ($)", "Upload my own CSV"],
        label_visibility="collapsed",
    )

    uploaded = None
    if source != "Generated sample (₹)":
        uploaded = st.file_uploader("Upload CSV", type="csv", label_visibility="collapsed")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
currency = "₹"
cleaning_report = None
data: pd.DataFrame | None = None

try:
    if source.startswith("Superstore"):
        currency = "$"
        if uploaded is not None:
            data, cleaning_report = clean_superstore(read_csv_flexible(uploaded))
        else:
            found = sorted(glob.glob("data/*uperstore*.csv"))
            if found:
                data, cleaning_report = load_superstore(found[0])
                st.sidebar.caption(f"Loaded `{found[0]}`")
            else:
                st.sidebar.info(
                    "Place the Superstore CSV in the `data/` folder, or upload it above. "
                    "Showing generated sample data in the meantime."
                )
    elif source.startswith("Upload") and uploaded is not None:
        raw = read_csv_flexible(uploaded)
        if looks_like_superstore(raw):
            data, cleaning_report = clean_superstore(raw)
            currency = "$"
        else:
            data = validate_sales_data(raw)
except ValueError as exc:
    st.sidebar.error(str(exc))
    st.sidebar.caption("Required columns: " + ", ".join(REQUIRED_COLUMNS))

if data is None:
    data, currency = load_sample(), "₹"
    cleaning_report = None

# ---------------------------------------------------------------------------
# Sidebar — filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.markdown("**Filters**")

    min_d = data["date"].min().date()
    max_d = data["date"].max().date()
    default_start = max(min_d, (pd.Timestamp(max_d) - pd.Timedelta(days=89)).date())

    picked = st.date_input(
        "Date range",
        (default_start, max_d),
        min_value=min_d,
        max_value=max_d,
    )
    if isinstance(picked, (tuple, list)):
        start, end = picked[0], picked[-1]
    else:
        start = end = picked
    start, end = pd.Timestamp(start), pd.Timestamp(end)

    filters: dict = {}
    for col, label in [
        ("region", "Region"),
        ("category", "Category"),
        ("channel", "Channel"),
        ("customer_segment", "Segment"),
    ]:
        options = sorted(data[col].dropna().unique())
        filters[col] = st.multiselect(label, options, default=options)

# ---------------------------------------------------------------------------
# Sidebar — AI configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.markdown("**AI Assistant**")

    provider = st.selectbox(
        "Provider",
        list(PROVIDERS),
        format_func=lambda k: PROVIDERS[k]["label"],
    )

    env_key = get_env_key(PROVIDERS[provider]["env"])
    raw_key = st.text_input(
        "API key",
        type="password",
        value="",
        key=f"api_key_{provider}",
        placeholder="Paste your key here…",
        help=(
            f"{PROVIDERS[provider]['hint']}\n\n"
            "The key is used only for the AI summary and Q&A. "
            "All other features work without one."
        ),
    )
    api_key = raw_key.strip() or env_key.strip() or None
    if env_key and not raw_key.strip():
        st.caption("Using the deployment API key (kept on the server).")

    # --- live key status ---
    if api_key:
        cache_key = f"_key_status_{provider}"
        # Keep only a non-reversible fingerprint in session state.  Streamlit
        # reruns the script on interaction, so this avoids repeat checks.
        # User-entered keys still live in their password widget session state.
        key_fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        prev_fingerprint = st.session_state.get(f"_key_fingerprint_{provider}", "")
        if key_fingerprint != prev_fingerprint:
            with st.spinner("Checking key…"):
                is_usable, key_msg = verify_api_key(provider, api_key)
            st.session_state[cache_key] = (is_usable, key_msg)
            st.session_state[f"_key_fingerprint_{provider}"] = key_fingerprint

        is_usable, key_msg = st.session_state.get(cache_key, (True, None))
        if is_usable:
            if key_msg:
                st.warning(key_msg, icon="⏳")
            else:
                st.success("Key verified ✓", icon="🔑")
        else:
            st.error(key_msg, icon="🚫")
            api_key = None  # only clear if explicitly an invalid key
    else:
        st.caption(f"No key — {PROVIDERS[provider]['hint']}")

# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
mask = pd.Series(True, index=data.index)
for col, sel in filters.items():
    mask &= data[col].isin(sel)
dim_df = data[mask]  # dimension-filtered (forecast uses full history)

cur = dim_df[(dim_df["date"] >= start) & (dim_df["date"] <= end)]
span = end - start + pd.Timedelta(days=1)
prev = dim_df[(dim_df["date"] >= start - span) & (dim_df["date"] < start)]

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("# Sales Intelligence Dashboard")
st.caption(
    f"{start:%d %b %Y} – {end:%d %b %Y} · "
    f"compared with the previous {span.days} days"
)

# Reserve KPI slot above tabs
kpi_placeholder = st.empty()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_over, tab_prod, tab_fc, tab_anom, tab_ai, tab_data = st.tabs(
    ["Overview", "Products & Regions", "Forecast", "Anomalies", "AI Insights", "Data & EDA"]
)

# ---------------------------------------------------------------------------
# Guard — nothing to show
# ---------------------------------------------------------------------------
if cur.empty:
    st.warning("No data matches the current filters. Try widening the date range or selections.")
    st.stop()

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------
t, p = totals(cur), totals(prev)
with kpi_placeholder.container():
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Revenue", fmt(t["revenue"], currency), delta_pct(t["revenue"], p["revenue"]))
    k2.metric("Profit", fmt(t["profit"], currency), delta_pct(t["profit"], p["profit"]))
    k3.metric(
        "Margin",
        f"{t['margin']:.1f}%",
        f"{t['margin'] - p['margin']:+.1f} pts" if p["revenue"] else None,
    )
    k4.metric("Orders", f"{t['orders']:,}", delta_pct(t["orders"], p["orders"]))
    k5.metric("Avg order value", fmt(t["aov"], currency), delta_pct(t["aov"], p["aov"]))

# ---------------------------------------------------------------------------
# Tab: Overview
# ---------------------------------------------------------------------------
_CHART_LAYOUT = dict(margin=dict(t=36, b=10, l=10, r=10), plot_bgcolor="rgba(0,0,0,0)")

with tab_over:
    gran = st.radio("Granularity", ["Daily", "Weekly", "Monthly"], index=1, horizontal=True)
    rule = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}[gran]
    trend = cur.set_index("date")[["revenue", "profit"]].resample(rule).sum().reset_index()

    fig = go.Figure()
    fig.add_bar(x=trend["date"], y=trend["revenue"], name="Revenue", marker_color="#2563EB")
    fig.add_scatter(
        x=trend["date"], y=trend["profit"], name="Profit",
        line=dict(color="#F59E0B", width=2.5),
    )
    fig.update_layout(
        height=370, yaxis_title=currency,
        legend=dict(orientation="h", y=1.08),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)

    reg = cur.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue")
    c1.plotly_chart(
        px.bar(reg, x="revenue", y="region", orientation="h", title="Revenue by region",
               color_discrete_sequence=["#2563EB"])
        .update_layout(height=300, **_CHART_LAYOUT),
        use_container_width=True,
    )

    leaf = "sub_category" if "sub_category" in cur.columns else "product"
    cat = cur.groupby(["category", leaf], as_index=False)["revenue"].sum()
    c2.plotly_chart(
        px.treemap(
            cat, path=["category", leaf], values="revenue",
            title=f"Revenue mix · category → {leaf.replace('_', ' ')}",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        .update_layout(height=300, **_CHART_LAYOUT),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Tab: Products & Regions
# ---------------------------------------------------------------------------
with tab_prod:
    c1, c2 = st.columns(2)

    prods = (
        cur.groupby("product")
        .agg(revenue=("revenue", "sum"), profit=("profit", "sum"))
        .reset_index()
    )
    prods["margin %"] = prods["profit"] / prods["revenue"] * 100
    top = prods.sort_values("revenue", ascending=False).head(10).sort_values("revenue")
    c1.plotly_chart(
        px.bar(
            top, x="revenue", y="product", orientation="h",
            color="margin %", color_continuous_scale="RdYlGn",
            title="Top 10 products by revenue (colour = margin %)",
        )
        .update_layout(height=400, **_CHART_LAYOUT),
        use_container_width=True,
    )

    heat = (
        cur.groupby(["region", "category"])
        .agg(r=("revenue", "sum"), p=("profit", "sum"))
        .reset_index()
    )
    heat["margin"] = heat["p"] / heat["r"] * 100
    hm = heat.pivot(index="region", columns="category", values="margin")
    c2.plotly_chart(
        px.imshow(
            hm, text_auto=".1f", color_continuous_scale="RdYlGn",
            aspect="auto", title="Profit margin % — region × category",
        )
        .update_layout(height=400, **_CHART_LAYOUT),
        use_container_width=True,
    )

    c3, c4 = st.columns(2)

    ch = cur.groupby(["channel", "customer_segment"], as_index=False)["revenue"].sum()
    c3.plotly_chart(
        px.bar(
            ch, x="channel", y="revenue", color="customer_segment",
            title="Revenue by channel & segment",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        .update_layout(height=320, **_CHART_LAYOUT),
        use_container_width=True,
    )

    band = cur.assign(
        discount_band=pd.cut(
            cur["discount"],
            [-0.01, 0, 0.05, 0.10, 0.15, 0.20, 1.0],
            labels=["0%", "≤5%", "≤10%", "≤15%", "≤20%", ">20%"],
        )
    )
    db = (
        band.groupby("discount_band", observed=True)
        .agg(r=("revenue", "sum"), p=("profit", "sum"))
        .reset_index()
    )
    db["margin %"] = db["p"] / db["r"] * 100
    c4.plotly_chart(
        px.line(
            db, x="discount_band", y="margin %", markers=True,
            title="Does discounting erode margin?",
            color_discrete_sequence=["#2563EB"],
        )
        .update_layout(height=320, **_CHART_LAYOUT),
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# Tab: Forecast
# ---------------------------------------------------------------------------
with tab_fc:
    st.markdown("### Monthly Revenue Forecast")
    horizon = st.slider("Months ahead", 3, 12, 6)
    res = cached_forecast(dim_df, horizon)

    if res is None:
        st.info(
            "At least 6 full months of history are needed for a forecast. "
            "Try widening the filter selection."
        )
    else:
        hist, fc = res["history"], res["forecast"]
        fig = go.Figure()
        fig.add_scatter(
            x=hist.index, y=hist.values, name="Actual",
            line=dict(color="#2563EB", width=2.5),
        )
        fig.add_scatter(
            x=fc.index, y=fc["upper"],
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        )
        fig.add_scatter(
            x=fc.index, y=fc["lower"],
            fill="tonexty", fillcolor="rgba(245,158,11,0.15)",
            line=dict(width=0), name="~95% band", hoverinfo="skip",
        )
        fig.add_scatter(
            x=fc.index, y=fc["forecast"], name="Forecast",
            line=dict(color="#F59E0B", width=2.5, dash="dash"),
        )
        fig.update_layout(
            height=400, yaxis_title=f"{currency} / month",
            legend=dict(orientation="h", y=1.08),
            **_CHART_LAYOUT,
        )
        st.plotly_chart(fig, use_container_width=True)

        m1, m2, m3 = st.columns(3)
        m1.metric(f"Next {horizon} months (total)", fmt(fc["forecast"].sum(), currency))
        m2.metric("Next month", fmt(fc["forecast"].iloc[0], currency))
        m3.metric(
            "Backtest error (last 3 months)",
            f"{res['backtest_mape'] * 100:.1f}% MAPE"
            if res["backtest_mape"] is not None
            else "n/a (need 27+ months)",
        )

        notes = [
            "Method: damped-trend Holt-Winters"
            + (" with multiplicative yearly seasonality." if res["seasonal"] else ".")
        ]
        if res["partial_month_excluded"]:
            notes.append("Current (incomplete) month excluded from training.")
        notes.append(
            "The shaded band is an approximation — not a formal prediction interval. "
            "Forecast respects the sidebar filters but ignores the date range."
        )
        st.caption("  ".join(notes))

        with st.expander("Forecast table"):
            st.dataframe(fc.round(0).rename_axis("Month"), use_container_width=True)

# ---------------------------------------------------------------------------
# Tab: Anomalies
# ---------------------------------------------------------------------------
with tab_anom:
    sens = st.select_slider(
        "Detection sensitivity", ["Low", "Medium", "High"], value="Medium"
    )
    contamination = {"Low": 0.005, "Medium": 0.01, "High": 0.02}[sens]
    anom_all = cached_anomalies(dim_df, contamination)

    if anom_all.empty:
        st.info("Not enough data to run anomaly detection.")
    else:
        unit = "weeks" if anom_all["freq"].iloc[0] == "W" else "days"
        st.markdown(f"### Unusual {unit.capitalize()} — Isolation Forest")

        anom_cur = anom_all[
            (anom_all.index >= start) & (anom_all.index <= end)
        ]
        view = st.radio("View", ["Selected date range", "Full history"], horizontal=True)
        plot = anom_cur if view == "Selected date range" else anom_all
        flagged = plot[plot["is_anomaly"]]

        fig = go.Figure()
        fig.add_scatter(
            x=plot.index, y=plot["revenue"],
            name=f"Revenue per {unit[:-1]}",
            line=dict(color="#2563EB", width=1.5),
        )
        fig.add_scatter(
            x=plot.index, y=plot["expected"],
            name="Rolling median",
            line=dict(color="#9CA3AF", dash="dot", width=1.5),
        )
        if not flagged.empty:
            fig.add_scatter(
                x=flagged.index, y=flagged["revenue"],
                mode="markers", name="Anomaly",
                marker=dict(color="#EF4444", size=10, symbol="diamond"),
            )
        fig.update_layout(
            height=390, legend=dict(orientation="h", y=1.08), **_CHART_LAYOUT
        )
        st.plotly_chart(fig, use_container_width=True)

        if flagged.empty:
            st.success(f"No unusual {unit} in this view.", icon="✅")
        else:
            tbl = flagged[["type", "revenue", "expected", "deviation_pct", "orders"]].copy()
            tbl.index = tbl.index.strftime("%d %b %Y")
            tbl.columns = ["Type", "Revenue", "Expected", "Deviation %", "Orders"]
            st.dataframe(tbl.round(0), use_container_width=True)

        st.caption(
            "Each period is compared with a rolling median so growth and seasonality "
            "don't trigger false alarms. Only deviations above 40% are marked."
            + (
                "  Sales are sparse, so weekly totals are used."
                if unit == "weeks"
                else ""
            )
        )

# ---------------------------------------------------------------------------
# Tab: AI Insights
# ---------------------------------------------------------------------------
with tab_ai:
    anomalies_for_facts = cached_anomalies(dim_df, 0.01)
    if not anomalies_for_facts.empty:
        anomalies_for_facts = anomalies_for_facts[
            (anomalies_for_facts.index >= start)
            & (anomalies_for_facts.index <= end)
        ]
    facts = build_facts(cur, prev, anomalies_for_facts, currency)
    # A summary belongs to one exact filtered view.  Keeping this signature prevents
    # an earlier summary from being presented as insight for newly selected filters.
    summary_signature = json.dumps(facts, sort_keys=True, default=str)

    # -- Executive summary --
    st.markdown("### Executive Summary")

    if api_key:
        btn_label = f"Generate with {PROVIDERS[provider]['label']}"
    else:
        btn_label = "Generate summary (rule-based — add an API key for AI)"

    if st.button(btn_label, type="primary"):
        with st.spinner("Analysing…"):
            st.session_state["summary"] = {
                "content": ai_summary(facts, api_key, provider),
                "signature": summary_signature,
            }

    saved_summary = st.session_state.get("summary")
    if isinstance(saved_summary, dict) and saved_summary.get("signature") == summary_signature:
        text, source_used = saved_summary["content"]
        st.markdown(text)
        if source_used in PROVIDERS:
            st.caption(f"Generated by {PROVIDERS[source_used]['label']} from aggregate figures only.")
        else:
            st.caption("Generated by deterministic rules from aggregate figures.")

    # -- Q&A --
    @st.fragment
    def render_qa():
        st.divider()
        st.markdown("### Ask Your Data")

        with st.form("qa_form"):
            q = st.text_input(
                "Question",
                placeholder="Which region has the best margin, and why is it outperforming?",
            )
            submitted = st.form_submit_button("Ask", type="secondary")

        if submitted and q.strip():
            question = q.strip()
            context = cached_qa_context(cur, question)
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant"):
                st.write_stream(
                    stream_answer_question(
                        question, cur, api_key, provider, currency, context=context
                    )
                )

        st.caption(
            "Only aggregated tables (totals by region, category, product, etc.) are sent to the model — "
            "never individual orders, customer names, or IDs."
        )

    render_qa()

# ---------------------------------------------------------------------------
# Tab: Data & EDA
# ---------------------------------------------------------------------------
with tab_data:
    st.markdown("### Data quality and analytical scope")
    st.caption(
        "This tab makes the data preparation visible so that dashboard results can be reviewed, "
        "not just consumed."
    )

    d1, d2, d3 = st.columns(3)
    d1.metric("Rows in active data", f"{len(data):,}")
    d2.metric("Date coverage", f"{data['date'].min():%d %b %Y} – {data['date'].max():%d %b %Y}")
    d3.metric("Missing values", f"{int(data.isna().sum().sum()):,}")

    if cleaning_report is not None:
        st.markdown("#### Cleaning report")
        st.dataframe(cleaning_report, hide_index=True, use_container_width=True)
    else:
        st.info(
            "You are viewing the generated sample data. Upload a Superstore CSV to see its "
            "row-level cleaning report."
        )

    st.markdown("#### Selected-data profile")
    profile = (
        cur.describe(include="all")
        .transpose()
        .reset_index(names="Field")
    )
    st.dataframe(profile, hide_index=True, use_container_width=True)
