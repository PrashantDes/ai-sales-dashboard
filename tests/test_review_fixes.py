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
    elif provider == "groq":
        monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=factory))
    else:
        monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=factory))


@pytest.mark.parametrize("provider", ["gemini", "anthropic", "groq"])
def test_verification_checks_provider_metadata(monkeypatch, provider):
    calls = []
    def list_models(**kwargs):
        calls.append(kwargs)
        return iter([SimpleNamespace(name="model")])
    install_provider(monkeypatch, provider, SimpleNamespace(list=list_models))
    assert ai.verify_api_key(provider, "key") == (True, None)
    assert len(calls) == 1


@pytest.mark.parametrize("provider", ["gemini", "anthropic", "groq"])
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
            Client=lambda **kwargs: SimpleNamespace(models=SimpleNamespace(generate_content_stream=stream, list=lambda **kwargs: [SimpleNamespace(name="models/fallback", supported_actions=["generateContent"])])),
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
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(ai, "verify_api_key", lambda *args: (True, None))
    captured = []
    def answer(question, df, api_key, provider, currency, context=None, model_override=None):
        captured.append((df.copy(), api_key, context))
        yield "Test answer"
    monkeypatch.setattr(ai, "stream_answer_question", answer)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=40).run()
    assert not at.exception
    at.selectbox[0].select("gemini").run()
    key_input = next(w for w in at.text_input if w.label == "API key")
    assert key_input.value == ""
    assert "server-only-test-secret" not in str(key_input.proto)
    dates = (pd.Timestamp("2026-09-01").date(), pd.Timestamp("2026-09-30").date())
    at.date_input[0].set_value(dates).run()
    at.toggle[0].set_value(True).run()
    at.session_state["dashboard_tabs"] = "AI Insights"
    at.run()
    next(w for w in at.text_input if w.label == "Question").set_value("Revenue by region?")
    next(w for w in at.button if w.label == "Ask").click().run()
    assert not at.exception
    frame, key, context = captured[-1]
    assert frame.date.min() >= pd.Timestamp(dates[0])
    assert frame.date.max() <= pd.Timestamp(dates[1])
    assert key == "server-only-test-secret"
    assert "SELECTED PERIOD: 2026-09-01 to 2026-09-30" in context


def test_gemini_candidates_only_use_advertised_text_models():
    models = [SimpleNamespace(name="models/flash-current", supported_actions=["generateContent"]),
              SimpleNamespace(name="models/image-model", supported_actions=["generateContent"]),
              SimpleNamespace(name="models/embed", supported_actions=["embedContent"])]
    client = SimpleNamespace(models=SimpleNamespace(list=lambda **kwargs: models))
    assert ai._gemini_candidates(client, "chosen") == ["chosen", "flash-current"]


@pytest.mark.parametrize("streaming", [False, True])
def test_gemini_preserves_overload_when_fallback_is_missing(monkeypatch, streaming):
    import google
    class ClientError(Exception):
        code = 404
    class ServerError(Exception):
        code = 503
    calls = []
    pauses = []
    def generate(**kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "primary":
            raise ServerError("503 unavailable secret-not-for-display")
        raise ClientError("model not found")
    sdk = SimpleNamespace(
        Client=lambda **kwargs: SimpleNamespace(models=SimpleNamespace(
            list=lambda **kwargs: [SimpleNamespace(name="models/fallback", supported_actions=["generateContent"])],
            generate_content=generate, generate_content_stream=generate)),
        errors=SimpleNamespace(ClientError=ClientError, ServerError=ServerError),
        types=SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs),
    )
    monkeypatch.setattr(google, "genai", sdk, raising=False)
    monkeypatch.setitem(sys.modules, "google.genai", sdk)
    monkeypatch.setattr(ai.time, "sleep", pauses.append)
    with pytest.raises(ServerError) as caught:
        if streaming:
            list(ai._stream_gemini("key", "primary", "system", "question", 100))
        else:
            ai._call_gemini("key", "primary", "system", "question", 100)
    assert pauses == [1]
    assert calls[-1] == "fallback"
    message = ai._classify_error(caught.value, "gemini")
    assert "switch providers" in message
    assert "secret-not-for-display" not in message


@pytest.mark.parametrize("streaming", [False, True])
def test_groq_dispatch_and_request(monkeypatch, streaming):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        if kwargs.get("stream"):
            return nullcontext(iter([
                SimpleNamespace(choices=[]),
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))]),
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Hello "))]),
                SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="Groq"))]),
            ]))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" Hello Groq "))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=lambda **kwargs: nullcontext(client)))
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setattr(ai, "_MODEL_CACHE", {})
    if streaming:
        answer = "".join(ai._stream_llm("groq", "test-key", "system", "question", 123))
    else:
        answer = ai._call_llm("groq", "test-key", "system", "question", 123)
    assert answer == "Hello Groq"
    assert calls[0]["model"] == "test-model"
    assert calls[0]["max_completion_tokens"] == 123
    assert calls[0]["messages"] == [{"role": "system", "content": "system"}, {"role": "user", "content": "question"}]


def test_groq_partial_stream_failure_does_not_restart(monkeypatch):
    calls = []
    def chunks():
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="partial"))])
        raise RuntimeError("connection interrupted")
    def create(**kwargs):
        calls.append(kwargs)
        return nullcontext(chunks())
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=lambda **kwargs: nullcontext(client)))
    stream = ai._stream_groq("key", "model", "system", "question", 100)
    assert next(stream) == "partial"
    with pytest.raises(RuntimeError, match="interrupted"):
        next(stream)
    assert len(calls) == 1


def test_groq_error_does_not_expose_key():
    message = ai._classify_error(RuntimeError("invalid_api_key token=secret"), "groq")
    assert "Invalid Groq API key" in message
    assert "secret" not in message


def test_missing_provider_dependency_explains_installation():
    message = ai._classify_error(ModuleNotFoundError("No module named groq"), "groq")
    assert "dependency is missing" in message
    assert "python -m pip install -r requirements.txt" in message
    assert "billing" not in message


@pytest.mark.parametrize("streaming", [False, True])
def test_groq_retired_model_falls_back_and_caches_working_model(monkeypatch, streaming):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        if kwargs["model"] == "retired":
            raise RuntimeError("model_decommissioned: model is no longer available")
        if streaming:
            return nullcontext(iter([SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="answer"))])]))
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="answer"))])
    models = [SimpleNamespace(id="whisper-large-v3", active=True),
              SimpleNamespace(id="openai/gpt-oss-20b", active=True),
              SimpleNamespace(id="groq/compound", active=True)]
    client = SimpleNamespace(models=SimpleNamespace(list=lambda: SimpleNamespace(data=models)),
                             chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=lambda **kwargs: nullcontext(client)))
    monkeypatch.setattr(ai, "_MODEL_CACHE", {})
    if streaming:
        answer = "".join(ai._stream_groq("test-key", "retired", "system", "question", 100))
    else:
        answer = ai._call_groq("test-key", "retired", "system", "question", 100)
    assert answer == "answer"
    assert [c["model"] for c in calls] == ["retired", "openai/gpt-oss-20b"]
    assert calls[-1]["reasoning_effort"] == "low"
    assert calls[-1]["include_reasoning"] is False
    assert "reasoning_format" not in calls[-1]
    assert calls[-1]["max_completion_tokens"] >= 2048
    assert ai.resolve_provider_model("groq", "test-key") == "openai/gpt-oss-20b"


@pytest.mark.parametrize("message", ["401 unauthorized", "429 rate limit", "400 invalid parameter"])
def test_groq_does_not_switch_models_for_unrelated_errors(monkeypatch, message):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        raise RuntimeError(message)
    client = SimpleNamespace(
        models=SimpleNamespace(list=lambda: SimpleNamespace(data=[SimpleNamespace(id="openai/gpt-oss-20b")])),
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=lambda **kwargs: nullcontext(client)))
    with pytest.raises(RuntimeError, match=message):
        ai._call_groq("key", "model", "system", "question", 100)
    assert len(calls) == 1
