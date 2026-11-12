"""Sales Intelligence Dashboard — Streamlit application.

Run:  streamlit run app.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
from datetime import date, timedelta
from typing import cast

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from sales_ai.ai import (
    PROVIDERS,
    ai_summary,
    build_facts,
    context_tables,
    detect_anomalies,
    forecast_revenue,
    money,
    rule_based_summary,
    stream_answer_question,
    verify_api_key,
)
from sales_ai.cleaning import clean_superstore, looks_like_superstore, read_csv_flexible
from sales_ai.data import REQUIRED_COLUMNS, generate_sales_data, validate_sales_data
from sales_ai.decisions import decision_brief

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
    return None if not prev else f"{(cur - prev) / abs(prev) * 100:+.1f}%"


def fmt(x: float, currency: str) -> str:
    return money(x, currency)


def remember_widget(name: str) -> None:
    """Keep chart settings when Streamlit removes a hidden tab's widgets."""
    st.session_state[name] = st.session_state[f"_widget_{name}"]


@st.cache_data(show_spinner="Generating sample data…")
def load_sample() -> pd.DataFrame:
    return generate_sales_data()


@st.cache_data(show_spinner="Cleaning data…")
def load_superstore(path: str, modified_ns: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    return clean_superstore(read_csv_flexible(path))


@st.cache_data(show_spinner=False, max_entries=16)
def cached_forecast(df: pd.DataFrame, horizon: int):
    return forecast_revenue(df, horizon)


@st.cache_data(show_spinner=False, max_entries=16)
def cached_anomalies(df: pd.DataFrame, contamination: float):
    return detect_anomalies(df, contamination)


@st.cache_data(show_spinner=False, max_entries=16)
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
        ["Generated sample (₹)", "Superstore CSV ($)", "Upload my own CSV", "Real-data SQL (GBP)"],
        label_visibility="collapsed",
    )

    assert source is not None
    if source == "Real-data SQL (GBP)":
        from sales_ai.retail_view import render_retail_view
        st.caption("Read-only historical analysis; no AI provider calls.")

    uploaded = None
    if source != "Generated sample (₹)" and source != "Real-data SQL (GBP)":
        uploaded = st.file_uploader("Upload CSV", type="csv", label_visibility="collapsed")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
if source == "Real-data SQL (GBP)":
    render_retail_view()
    st.stop()

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
                data, cleaning_report = load_superstore(found[0], os.stat(found[0]).st_mtime_ns)
                st.sidebar.caption(f"Loaded `{found[0]}`")
            else:
                st.sidebar.info(
                    "Place the Superstore CSV in the `data/` folder, or upload it above. "
                    "Upload a file to continue."
                )
                st.stop()
    elif source.startswith("Upload") and uploaded is not None:
        raw = read_csv_flexible(uploaded)
        if looks_like_superstore(raw):
            data, cleaning_report = clean_superstore(raw)
            currency = "$"
        else:
            data = validate_sales_data(raw)
            cleaning_report = pd.DataFrame(data.attrs.get("cleaning_report", []))
except ValueError as exc:
    st.sidebar.error(str(exc))
    st.sidebar.caption("Required columns: " + ", ".join(REQUIRED_COLUMNS))
    st.error("The file could not be loaded. Correct the reported issue and upload it again.")
    st.stop()

if data is None and not source.startswith("Generated"):
    st.info("Upload a CSV in the sidebar to begin, or choose Generated sample.")
    st.stop()

if data is None:
    data, currency = load_sample(), "₹"
    cleaning_report = None

# ---------------------------------------------------------------------------
# Sidebar — filters
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    st.markdown("**Filters**")

    min_d = date.fromisoformat(str(data["date"].min())[:10])
    max_d = date.fromisoformat(str(data["date"].max())[:10])
    default_start = max(min_d, max_d - timedelta(days=89))

    date_memory = st.session_state.get(f"dashboard_dates_{source}", (default_start, max_d))
    if len(date_memory) != 2 or date_memory[0] < min_d or date_memory[1] > max_d:
        date_memory = (default_start, max_d)
    picked = st.date_input(
        "Date range",
        date_memory,
        min_value=min_d,
        max_value=max_d,
        key=f"_widget_dashboard_dates_{source}",
    )
    if isinstance(picked, (tuple, list)):
        if len(picked) != 2:
            st.info("Choose both a start date and an end date.")
            st.stop()
        start, end = picked
    else:
        start = end = picked
    st.session_state[f"dashboard_dates_{source}"] = (start, end)
    start, end = cast(pd.Timestamp, pd.Timestamp(start)), cast(pd.Timestamp, pd.Timestamp(end))

    filters: dict = {}
    for col, label in [
        ("region", "Region"),
        ("category", "Category"),
        ("channel", "Channel"),
        ("customer_segment", "Segment"),
    ]:
        options = sorted(data[col].dropna().unique())
        memory_key = f"dashboard_filter_{source}_{col}"
        defaults = [value for value in st.session_state.get(memory_key, options) if value in options]
        filters[col] = st.multiselect(label, options, default=defaults, key=f"_widget_{memory_key}")
        st.session_state[memory_key] = filters[col]

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

    assert provider is not None
    use_online_ai = st.toggle("Use online AI", value=False, help="Optional. Local insights work without a key or network access.")
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
    api_key = (raw_key.strip() or env_key.strip() or None) if use_online_ai else None
    if use_online_ai and env_key and not raw_key.strip():
        st.caption("Using the deployment API key (kept on the server).")

    model_override = get_env_key(PROVIDERS[provider]["model_env"]).strip() or None
    if use_online_ai:
        if model_override:
            st.caption(f"Model override: {model_override}")
        if api_key:
            key_fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            status_key = f"_key_status_{provider}"
            if st.button("Check connection"):
                with st.spinner("Checking provider metadata..."):
                    st.session_state[status_key] = (key_fingerprint, verify_api_key(provider, api_key))
            status = st.session_state.get(status_key)
            if status and status[0] == key_fingerprint:
                usable, message = status[1]
                if not usable:
                    st.error(message)
                    api_key = None
                elif message:
                    st.warning(message)
                else:
                    st.success("Credential accepted. Generation depends on model access and quota.")
        else:
            st.caption("Enter a key to enable online answers.")
    else:
        st.caption("Local mode: no sales data is sent to an AI provider.")

# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
mask = pd.Series(True, index=data.index)
for col, sel in filters.items():
    mask &= data[col].isin(sel)
dim_df = data[mask]  # dimension-filtered (forecast uses full history)

cur = dim_df[(dim_df["date"] >= start) & (dim_df["date"] <= end)]
span = cast(pd.Timedelta, end - start + pd.Timedelta(days=1))
prev = dim_df[(dim_df["date"] >= start - span) & (dim_df["date"] < start)]

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("# Sales Intelligence Dashboard")
if source.startswith("Generated"):
    st.caption("Synthetic demo | seed 42 | not real customer or commercial results")
else:
    st.caption("Uploaded data | review the cleaning report in Data & EDA")
st.caption(
    f"{start:%d %b %Y} – {end:%d %b %Y} · "
    f"compared with the previous {span.days} days"
)

# Reserve KPI slot above tabs
kpi_placeholder = st.empty()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
if "dashboard_tabs" not in st.session_state:
    st.session_state["dashboard_tabs"] = st.session_state.get("dashboard_active_tab", "Overview")
tab_over, tab_prod, tab_fc, tab_anom, tab_ai, tab_data = st.tabs(
    ["Overview", "Products & Regions", "Forecast", "Anomalies", "AI Insights", "Data & EDA"],
    key="dashboard_tabs", on_change="rerun",
)
st.session_state["dashboard_active_tab"] = st.session_state["dashboard_tabs"]

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
previous_covered = start.to_pydatetime().date() - timedelta(days=span.days) >= min_d
if not previous_covered:
    st.warning("The dataset does not cover the full comparison period. Previous-period changes are hidden.")
    p = {key: 0 for key in p}
comparison_prev = prev if previous_covered else prev.iloc[:0]
with kpi_placeholder.container():
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Revenue", fmt(t["revenue"], currency), delta_pct(t["revenue"], p["revenue"]))
    k2.metric("Recorded profit", fmt(t["profit"], currency), delta_pct(t["profit"], p["profit"]), help="Change = (current - previous) / absolute previous profit. A reduction in losses is a positive change.")
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
    if tab_over.open:
        st.markdown("### Decisions to review")
        brief = decision_brief(cur, comparison_prev, currency)
        for finding in brief["findings"]:
            with st.container(border=True):
                st.markdown(f"**{finding['title']}**")
                st.write(finding["evidence"])
                st.write("Suggested action: " + finding["action"])
                st.caption(finding["caveat"])
        st.download_button("Download decision brief", json.dumps({"period": [str(start.date()), str(end.date())], "filters": filters, "currency": currency, "brief": brief}, indent=2, default=str),
                           file_name="decision-brief.json", mime="application/json")
        gran = st.radio("Granularity", ["Daily", "Weekly", "Monthly"],
                        index=["Daily", "Weekly", "Monthly"].index(st.session_state.get("granularity", "Weekly")),
                        horizontal=True, key="_widget_granularity", on_change=remember_widget, args=("granularity",))
        assert gran is not None
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
        st.plotly_chart(fig, width="stretch")

        c1, c2 = st.columns(2)

        reg = cur.groupby("region", as_index=False)["revenue"].sum().sort_values("revenue")
        c1.plotly_chart(
            px.bar(reg, x="revenue", y="region", orientation="h", title="Revenue by region",
                   color_discrete_sequence=["#2563EB"])
            .update_layout(height=300, **_CHART_LAYOUT),
            width="stretch",
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
            width="stretch",
        )

# ---------------------------------------------------------------------------
# Tab: Products & Regions
# ---------------------------------------------------------------------------
with tab_prod:
    if tab_prod.open:
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
            width="stretch",
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
            width="stretch",
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
            width="stretch",
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
                title="Margin by discount band (association, not causation)",
                color_discrete_sequence=["#2563EB"],
            )
            .update_layout(height=320, **_CHART_LAYOUT),
            width="stretch",
        )

# ---------------------------------------------------------------------------
# Tab: Forecast
# ---------------------------------------------------------------------------
with tab_fc:
    if tab_fc.open:
        st.markdown("### Monthly Revenue Forecast")
        horizon = st.slider("Months ahead", 3, 12, st.session_state.get("forecast_horizon", 6),
                            key="_widget_forecast_horizon", on_change=remember_widget, args=("forecast_horizon",))
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
                line=dict(width=0), name="Approximate range", hoverinfo="skip",
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
            st.plotly_chart(fig, width="stretch")

            m1, m2, m3 = st.columns(3)
            m1.metric(f"Next {horizon} months (total)", fmt(fc["forecast"].sum(), currency))
            m2.metric("Next month", fmt(fc["forecast"].iloc[0], currency))
            evaluation = res["evaluation"]
            validation_wape = evaluation["selected_wape"] if evaluation else None
            m3.metric(
                "Validation WAPE (last 3 months)",
                f"{validation_wape * 100:.1f}%" if validation_wape is not None else "Not available",
            )
            st.caption("Selected method: " + res["method_label"])
            if evaluation:
                comparison = pd.DataFrame([
                    {"Method": "Holt-Winters", "MAE": evaluation["hw_mae"],
                     "WAPE %": evaluation["hw_wape"] * 100 if evaluation["hw_wape"] is not None else None},
                    {"Method": evaluation["baseline_label"], "MAE": evaluation["baseline_mae"],
                     "WAPE %": evaluation["baseline_wape"] * 100 if evaluation["baseline_wape"] is not None else None},
                ])
                st.dataframe(comparison.round(2), hide_index=True, width="stretch")
                st.caption(evaluation["note"] + " MAE is in currency units; WAPE is absolute error divided by total actual revenue. Lower is better.")
                with st.expander("Validation predictions"):
                    st.dataframe(res["holdout"].round(0), width="stretch")
            else:
                st.info("Fewer than 9 usable months: showing an unvalidated last-month baseline. At least 6 training months and 3 validation months are needed to compare methods.")
            notes = []
            if res["partial_month_excluded"]:
                notes.append("Trailing month excluded because observations end more than 3 days before month-end.")
            if res["first_month_may_be_partial"]:
                notes.append("The first month may be incomplete; verify export coverage before planning.")
            notes.append("The shaded band is a residual-based approximation, not a calibrated 95% interval. Missing interior months count as zero sales. Forecast uses all history under the dimension filters, independently of the date range.")
            st.caption(" ".join(notes))

            with st.expander("Forecast table"):
                st.dataframe(fc.round(0).rename_axis("Month"), width="stretch")

# ---------------------------------------------------------------------------
# Tab: Anomalies
# ---------------------------------------------------------------------------
with tab_anom:
    if tab_anom.open:
        sens = st.select_slider(
            "Detection sensitivity", ["Low", "Medium", "High"],
            value=st.session_state.get("sensitivity", "Medium"), key="_widget_sensitivity",
            on_change=remember_widget, args=("sensitivity",)
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
            view = st.radio("View", ["Selected date range", "Full history"],
                            index=["Selected date range", "Full history"].index(st.session_state.get("anomaly_view", "Selected date range")),
                            horizontal=True, key="_widget_anomaly_view", on_change=remember_widget, args=("anomaly_view",))
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
            st.plotly_chart(fig, width="stretch")

            if len(anom_all) < (30 if unit == "weeks" else 60):
                st.info("Insufficient history for detection: need 30 weekly or 60 daily periods. No anomaly assessment has been made.")
            elif flagged.empty:
                st.success(f"No unusual {unit} in this view.", icon="✅")
            else:
                tbl = flagged[["type", "revenue", "expected", "deviation_pct", "orders"]].copy()
                tbl.index = tbl.index.strftime("%d %b %Y")
                tbl.columns = ["Type", "Revenue", "Expected", "Deviation %", "Orders"]
                st.dataframe(tbl.round(0), width="stretch")

            st.caption(
                "Retrospective screening: a centered rolling median includes nearby future observations. "
                "This is not a live alert or proof of a cause. Sensitivity sets the Isolation Forest outlier fraction; "
                "only deviations above the 40% materiality heuristic are surfaced."
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
    if tab_ai.open:
        anomalies_for_facts = cached_anomalies(dim_df, 0.01)
        if not anomalies_for_facts.empty:
            anomalies_for_facts = anomalies_for_facts[
                (anomalies_for_facts.index >= start)
                & (anomalies_for_facts.index <= end)
            ]
        facts = build_facts(cur, comparison_prev, anomalies_for_facts, currency)
        # A summary belongs to one exact filtered view.  Keeping this signature prevents
        # an earlier summary from being presented as insight for newly selected filters.
        summary_signature = json.dumps(facts, sort_keys=True, default=str) + f"|{provider}|{bool(api_key)}|{model_override}"

        st.caption("Local insights are always available. Enable online AI in the sidebar for optional rewriting and Q&A.")
        # -- Executive summary --
        st.markdown("### Executive Summary")

        if api_key:
            btn_label = f"Generate with {PROVIDERS[provider]['label']}"
        else:
            btn_label = "Generate summary (rule-based — add an API key for AI)"

        st.markdown(rule_based_summary(facts))

        if st.button(btn_label, type="primary", disabled=not bool(api_key)):
            with st.spinner("Analysing…"):
                st.session_state["summary"] = {
                    "content": ai_summary(facts, api_key, provider, model_override=model_override),
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
                    placeholder="Which region has the highest recorded margin?",
                    disabled=not bool(api_key),
                )
                submitted = st.form_submit_button("Ask", type="secondary", disabled=not bool(api_key))

            if submitted and q.strip():
                question = q.strip()
                context = cached_qa_context(cur, question)
                with st.chat_message("user"):
                    st.write(question)
                with st.chat_message("assistant"):
                    st.write_stream(
                        stream_answer_question(
                            question, cur, api_key, provider, currency, context=context, model_override=model_override
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
    if tab_data.open:
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
            st.dataframe(cleaning_report, hide_index=True, width="stretch")
        else:
            st.info(
                "This reproducible sample is generated from explicit seasonality, growth, discount and "
                "outage assumptions. It demonstrates the workflow, not real commercial performance."
            )

        st.markdown("#### Selected-data profile")
        profile = (
            cur.describe(include="all")
            .transpose()
            .reset_index(names="Field")
        )
        st.dataframe(profile, hide_index=True, width="stretch")
