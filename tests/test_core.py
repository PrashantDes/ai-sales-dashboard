import pandas as pd
import pytest

from sales_ai.ai import (
    _classify_error,
    _text_model_rank,
    build_facts,
    context_tables,
    detect_anomalies,
    forecast_revenue,
    rule_based_summary,
)
from sales_ai.data import generate_sales_data, validate_sales_data


@pytest.fixture(scope="module")
def df():
    return generate_sales_data()


def test_generator_schema_and_math(df):
    assert len(df) > 20_000
    assert df["order_id"].is_unique
    assert ((df["revenue"] - df["cost"] - df["profit"]).abs() < 0.02).all()
    assert df["discount"].between(0, 0.2).all()


def test_forecast_shape_and_bounds(df):
    res = forecast_revenue(df, horizon=6)
    assert res is not None and len(res["forecast"]) == 6
    assert res["partial_month_excluded"] is True  # data ends mid-October
    f = res["forecast"]
    assert (f["lower"] <= f["forecast"]).all() and (f["forecast"] <= f["upper"]).all()
    assert res["backtest_mape"] < 0.25


def test_anomalies_find_injected_days(df):
    a = detect_anomalies(df, contamination=0.01)
    assert a["is_anomaly"].sum() >= 3
    assert set(a.loc[a["is_anomaly"], "type"]) <= {"spike", "drop"}


def test_facts_and_summary(df):
    cur = df[df["date"] >= "2026-08-01"]
    prev = df[(df["date"] >= "2026-05-01") & (df["date"] < "2026-08-01")]
    facts = build_facts(cur, prev)
    assert facts["totals"]["revenue"] > 0
    assert "Headline" in rule_based_summary(facts)


def test_validate_rejects_bad_schema():
    with pytest.raises(ValueError):
        validate_sales_data(pd.DataFrame({"date": ["2026-01-01"]}))


def test_provider_errors_do_not_echo_sensitive_exception_text():
    message = _classify_error(RuntimeError("token=do-not-display"), "gemini")
    assert "do-not-display" not in message
    assert "RuntimeError" in message


def test_model_not_found_error_is_actionable():
    message = _classify_error(
        RuntimeError("models/gemini-old is not found for API version v1beta"),
        "gemini",
    )
    assert "model unavailable" in message


def test_question_context_is_compact_and_relevant(df):
    context = context_tables(df, "Which product has the best margin?")
    assert "BY PRODUCT" in context
    assert "BY REGION" not in context
    assert "MONTHLY REVENUE" not in context
    assert "top 10" in context


def test_fast_models_rank_before_larger_models():
    assert _text_model_rank("gemini-flash-lite") < _text_model_rank("gemini-pro")


# ---- Superstore cleaning layer -------------------------------------------------
from io import BytesIO  # noqa: E402

from sales_ai.cleaning import clean_superstore, looks_like_superstore, read_csv_flexible  # noqa: E402
from tests.fake_superstore import make_fake_superstore  # noqa: E402


@pytest.fixture(scope="module")
def raw_ss():
    return make_fake_superstore()


def test_superstore_detected_and_cleaned(raw_ss):
    assert looks_like_superstore(raw_ss)
    clean, report = clean_superstore(raw_ss)
    assert len(clean) == len(raw_ss) - 1  # duplicate removed
    assert {"date", "order_id", "region", "category", "channel", "revenue", "profit", "cost"} <= set(clean.columns)
    assert ((clean["revenue"] - clean["cost"] - clean["profit"]).abs() < 1e-6).all()
    assert clean["order_id"].nunique() < len(clean)  # multi-line orders are preserved
    assert "Exact duplicate rows removed" in set(report["Step"])


def test_superstore_dayfirst_dates_detected(raw_ss):
    swapped = raw_ss.copy()
    d = pd.to_datetime(swapped["Order Date"], format="%m/%d/%Y")
    swapped["Order Date"] = d.dt.strftime("%d/%m/%Y")
    clean, _ = clean_superstore(swapped)
    assert clean["date"].min().year == 2014 and clean["date"].max().year <= 2017


def test_superstore_cp1252_roundtrip(raw_ss):
    buf = BytesIO(raw_ss.to_csv(index=False).encode("cp1252"))
    assert len(read_csv_flexible(buf)) == len(raw_ss)


def test_superstore_without_profit_gives_helpful_error(raw_ss):
    with pytest.raises(ValueError, match="Profit"):
        clean_superstore(raw_ss.drop(columns=["Profit", "Discount", "Quantity"]))


def test_pipeline_runs_on_superstore(raw_ss):
    clean, _ = clean_superstore(raw_ss)
    assert detect_anomalies(clean)["freq"].iloc[0] in {"D", "W"}
    assert forecast_revenue(clean, 6) is not None
    facts = build_facts(clean[clean["date"] >= "2017-10-01"], clean[clean["date"] < "2017-10-01"], currency="$")
    assert "$" in rule_based_summary(facts)
