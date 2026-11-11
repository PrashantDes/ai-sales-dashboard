"""Regression coverage for the project review fixes; no live API calls."""
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd
import pytest

import sales_ai.ai as ai
from sales_ai.cleaning import clean_superstore
from sales_ai.data import validate_sales_data
from tests.fake_superstore import make_fake_superstore


def sales_row(**overrides):
    row = dict(date="2026-01-31", order_id="1", region="North", city="Delhi",
               category="Office", product="Desk", channel="Website",
               customer_segment="Consumer", units=1, discount=0, revenue=100, cost=60)
    return {**row, **overrides}


def test_profit_strings_are_parsed_and_missing_profit_is_derived():
    result = validate_sales_data(pd.DataFrame([sales_row(profit="40")]))
    assert result.profit.sum() / result.revenue.sum() == 0.4
    assert validate_sales_data(pd.DataFrame([sales_row()])).profit.iloc[0] == 40


@pytest.mark.parametrize("profit", ["invalid", None, np.inf, -np.inf])
def test_invalid_profit_is_rejected(profit):
    with pytest.raises(ValueError, match="Profit"):
        validate_sales_data(pd.DataFrame([sales_row(profit=profit)]))


def test_declining_revenue_forecast_has_nonnegative_ordered_bounds():
    frame = pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=30, freq="MS") + pd.offsets.MonthEnd(0),
        "revenue": list(range(300, 0, -10)),
    })
    forecast = ai.forecast_revenue(frame)["forecast"]
    assert np.isfinite(forecast.to_numpy()).all()
    assert (forecast["lower"] >= 0).all()
    assert (forecast["lower"] <= forecast["forecast"]).all()
    assert (forecast["forecast"] <= forecast["upper"]).all()


def test_long_product_names_remain_distinct():
    raw = make_fake_superstore(2).iloc[:2].copy()
    raw["Product Name"] = ["a" * 45 + " first", "a" * 45 + " second"]
    clean, _ = clean_superstore(raw)
    assert clean["product"].nunique() == 2
    assert clean.groupby("product").revenue.sum().shape[0] == 2


def install_provider(monkeypatch, provider, models):
    client = SimpleNamespace(models=models, messages=models)
    factory = lambda **kwargs: nullcontext(client)
    if provider == "gemini":
        import google
        sdk = SimpleNamespace(Client=factory)
        monkeypatch.setattr(google, "genai", sdk, raising=False)
        monkeypatch.setitem(sys.modules, "google.genai", sdk)
    else:
        monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=factory))


@pytest.mark.parametrize("provider", ["gemini", "anthropic"])
def test_verification_checks_provider_metadata(monkeypatch, provider):
    calls = []
    def list_models(**kwargs):
        calls.append(kwargs)
        return iter([SimpleNamespace(name="model")])
    install_provider(monkeypatch, provider, SimpleNamespace(list=list_models))
    assert ai.verify_api_key(provider, "key") == (True, None)
    assert len(calls) == 1


@pytest.mark.parametrize("provider", ["gemini", "anthropic"])
def test_invalid_credentials_are_not_verified(monkeypatch, provider):
    def list_models(**kwargs):
        raise RuntimeError("401 unauthorized")
    install_provider(monkeypatch, provider, SimpleNamespace(list=list_models))
    usable, message = ai.verify_api_key(provider, "bogus-key")
    assert not usable
    assert "Invalid" in message


@pytest.mark.parametrize("provider", ["gemini", "anthropic"])
@pytest.mark.parametrize("partial", [True, False])
def test_stream_fallback_only_before_output(monkeypatch, provider, partial):
    calls = []
    class ClientError(Exception):
        pass
    def chunks():
        if partial:
            yield SimpleNamespace(text="partial answer") if provider == "gemini" else "partial answer"
        raise RuntimeError("connection interrupted")
    def stream(**kwargs):
        calls.append(kwargs["model"])
        if len(calls) == 1:
            result = chunks()
        else:
            result = iter([SimpleNamespace(text="fallback answer") if provider == "gemini" else "fallback answer"])
        return result if provider == "gemini" else nullcontext(SimpleNamespace(text_stream=result))
    if provider == "gemini":
        import google
        sdk = SimpleNamespace(
            Client=lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content_stream=stream)),
            errors=SimpleNamespace(ClientError=ClientError, ServerError=RuntimeError),
            types=SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs),
        )
        monkeypatch.setattr(google, "genai", sdk, raising=False)
        monkeypatch.setitem(sys.modules, "google.genai", sdk)
        iterator = ai._stream_gemini("key", "primary", "system", "question", 100)
    else:
        monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(
            Anthropic=lambda **kwargs: SimpleNamespace(messages=SimpleNamespace(stream=stream)),
            AuthenticationError=ClientError,
        ))
        iterator = ai._stream_anthropic("key", "primary", "system", "question", 100)
    if partial:
        assert next(iterator) == "partial answer"
        with pytest.raises(RuntimeError, match="interrupted"):
            next(iterator)
        assert len(calls) == 1
    else:
        assert "".join(iterator) == "fallback answer"
        assert len(calls) == 2


def test_ui_keeps_server_key_private_and_qa_uses_selected_period(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("GEMINI_API_KEY", "server-only-test-secret")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(ai, "verify_api_key", lambda *args: (True, None))
    captured = []
    def answer(question, df, api_key, provider, currency, context=None):
        captured.append((df.copy(), api_key, context))
        yield "Test answer"
    monkeypatch.setattr(ai, "stream_answer_question", answer)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40).run()
    assert not at.exception
    key_input = next(w for w in at.text_input if w.label == "API key")
    assert key_input.value == ""
    assert "server-only-test-secret" not in str(key_input.proto)
    dates = (pd.Timestamp("2026-09-01").date(), pd.Timestamp("2026-09-30").date())
    at.date_input[0].set_value(dates).run()
    next(w for w in at.text_input if w.label == "Question").set_value("Revenue by region?")
    next(w for w in at.button if w.label == "Ask").click().run()
    assert not at.exception
    frame, key, context = captured[-1]
    assert frame.date.min() >= pd.Timestamp(dates[0])
    assert frame.date.max() <= pd.Timestamp(dates[1])
    assert key == "server-only-test-secret"
    assert "SELECTED PERIOD: 2026-09-01 to 2026-09-30" in context
