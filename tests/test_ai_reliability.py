"""Regression tests for honest summaries, ranking context and model configuration."""
from contextlib import nullcontext
import sys
from types import SimpleNamespace

import pandas as pd
import pytest

import sales_ai.ai as ai


def test_margin_question_includes_low_revenue_winner_and_loser():
    rows = [dict(date=pd.Timestamp("2026-09-01"), order_id=str(i), product=f"Product {i}",
                 revenue=1000-i, profit=100, discount=0) for i in range(12)]
    rows += [dict(date=pd.Timestamp("2026-09-01"), order_id="winner", product="Small winner", revenue=1, profit=1, discount=0),
             dict(date=pd.Timestamp("2026-09-01"), order_id="loser", product="Small loser", revenue=1, profit=-1, discount=0)]
    context = ai.context_tables(pd.DataFrame(rows), "Which product has the highest and lowest margin?")
    assert "Small winner" in context and "Small loser" in context
    assert "HIGHEST MARGIN PRODUCT" in context and "LOWEST MARGIN PRODUCT" in context
    assert "14 groups" in context and "4 omitted" in context
    assert "margin_pct" in context


def test_small_dimensions_include_all_groups_and_margins():
    frame = pd.DataFrame(dict(date=[pd.Timestamp("2026-09-01")], order_id=["A"],
        region=["West"], revenue=[100], profit=[20], discount=[0]))
    context = ai.context_tables(frame, "Which region has the best margin?")
    assert "BY REGION (all groups)" in context
    assert "margin_pct" in context
    assert "HIGHEST MARGIN" not in context


@pytest.mark.parametrize("deep_margin,expected", [(10, "is lower"), (30, "is higher"), (20, "is unchanged")])
def test_discount_summary_direction_and_causality(deep_margin, expected):
    facts = dict(currency="$", totals=dict(revenue=100, margin=20), period="September",
        change_vs_previous_pct=dict(revenue=0),
        region={"West": {"share": 100}}, category={"Office": {"share": 100, "margin": 20}},
        margin_by_discount={"no discount": 20, "over 20%": deep_margin})
    text = ai.rule_based_summary(facts)
    assert expected in text
    assert "association" in text
    assert "compresses" not in text


def test_override_identity_isolated_and_env_changes_take_effect(monkeypatch):
    monkeypatch.setattr(ai, "_MODEL_CACHE", {})
    monkeypatch.setenv("GROQ_MODEL", "environment-model")
    assert ai.resolve_provider_model("groq", "key") == "environment-model"
    assert ai.resolve_provider_model("groq", "key", "secret-model") == "secret-model"
    ai._MODEL_CACHE[ai._model_cache_key("groq", "key", "secret-model")] = "working-fallback"
    assert ai.resolve_provider_model("groq", "key", "secret-model") == "working-fallback"
    assert ai.resolve_provider_model("groq", "key", "new-secret-model") == "new-secret-model"
    monkeypatch.setenv("GROQ_MODEL", "changed-environment")
    assert ai.resolve_provider_model("groq", "key") == "changed-environment"


def test_summary_and_question_forward_override(monkeypatch):
    received = []
    def summary(*args, **kwargs):
        received.append(kwargs["model_override"])
        return "summary"
    def stream(*args, **kwargs):
        received.append(kwargs["model_override"])
        yield "answer"
    monkeypatch.setattr(ai, "_call_llm", summary)
    monkeypatch.setattr(ai, "_stream_llm", stream)
    assert ai.ai_summary({"currency": "$"}, "key", "groq", model_override="configured")[0] == "summary"
    assert "".join(ai.stream_answer_question("question", pd.DataFrame(), "key", "groq", context="", model_override="configured")) == "answer"
    assert received == ["configured", "configured"]


@pytest.mark.parametrize("streaming", [False, True])
def test_anthropic_quota_does_not_try_other_models(monkeypatch, streaming):
    class QuotaError(Exception):
        status_code = 429
    class AuthError(Exception):
        pass
    calls = []
    def fail(**kwargs):
        calls.append(kwargs)
        raise QuotaError("Too many requests")
    sdk = SimpleNamespace(Anthropic=lambda **kwargs: SimpleNamespace(messages=SimpleNamespace(create=fail, stream=fail)),
                          AuthenticationError=AuthError)
    monkeypatch.setitem(sys.modules, "anthropic", sdk)
    with pytest.raises(QuotaError):
        if streaming:
            list(ai._stream_anthropic("key", "model", "system", "question", 100))
        else:
            ai._call_anthropic("key", "model", "system", "question", 100)
    assert len(calls) == 1


@pytest.mark.parametrize("current,expected", [(-50, 50), (-200, -100), (50, 150)])
def test_profit_change_preserves_direction_from_previous_loss(current, expected):
    assert ai._pct(current, -100) == expected
