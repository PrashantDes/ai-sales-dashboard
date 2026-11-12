"""Forecast evaluation tests use known signals and explicitly separate validation."""
import numpy as np
import pandas as pd
import pytest

import sales_ai.ai as ai


def monthly_rows(values):
    return pd.DataFrame({
        "date": pd.date_range("2023-01-01", periods=len(values), freq="MS") + pd.offsets.MonthEnd(0),
        "revenue": values,
    })


def test_seasonal_baseline_wins_when_it_is_exact():
    values = np.tile([100, 130, 90, 85, 110, 125, 100, 105, 140, 180, 200, 150], 3)
    result = ai.forecast_revenue(monthly_rows(values), 6)
    evaluation = result["evaluation"]
    assert result["method"] == "seasonal_naive"
    assert evaluation["baseline_mae"] == 0
    assert evaluation["selected_wape"] == 0
    np.testing.assert_allclose(result["forecast"]["forecast"], values[-12:-6])
    np.testing.assert_allclose(result["holdout"]["actual"], values[-3:])
    assert evaluation["training_months"] == 33


def test_holt_winters_must_beat_baseline_and_uses_no_holdout_during_fit(monkeypatch):
    values = np.arange(1, 19, dtype=float) * 100
    fitted_lengths = []
    class TrendFit:
        def __init__(self, series):
            self.series = series
            self.fittedvalues = series.copy()
        def forecast(self, horizon):
            return self.series.iloc[-1] + np.arange(1, horizon + 1) * 100
    def fit(series):
        fitted_lengths.append(len(series))
        return TrendFit(series)
    monkeypatch.setattr(ai, "_fit_hw", fit)
    result = ai.forecast_revenue(monthly_rows(values))
    assert fitted_lengths == [15, 18]  # validation fit precedes full-history refit
    assert result["method"] == "holt_winters"
    assert result["evaluation"]["selected_mae"] == 0
    assert result["evaluation"]["improvement_pct"] == 100
    assert result["holdout"].index[0] == pd.Timestamp("2024-04-01")
    assert result["forecast"].index[0] == pd.Timestamp("2024-07-01")


def test_zero_sales_do_not_create_infinite_percentage_errors():
    result = ai.forecast_revenue(monthly_rows(np.zeros(18)))
    assert result["evaluation"]["selected_wape"] is None
    assert result["backtest_mape"] is None
    assert result["evaluation"]["selected_mae"] == 0
    assert (result["forecast"] == 0).all().all()


def test_percentage_error_is_undefined_when_holdout_contains_zero():
    result = ai.forecast_revenue(monthly_rows([100] * 15 + [0, 50, 100]))
    assert result["backtest_mape"] is None
    assert np.isfinite(result["evaluation"]["selected_wape"])


def test_short_history_uses_explicit_unvalidated_baseline():
    result = ai.forecast_revenue(monthly_rows([100, 110, 120, 130, 140, 150]))
    assert result["method"] == "last_month"
    assert result["evaluation"] is None
    assert result["holdout"].empty
    assert (result["forecast"]["forecast"] == 150).all()


def test_fit_failure_keeps_baseline_available(monkeypatch):
    def fail(series):
        raise ValueError("cannot fit")
    monkeypatch.setattr(ai, "_fit_hw", fail)
    result = ai.forecast_revenue(monthly_rows(np.arange(1, 19) * 100))
    assert result["method"] == "seasonal_naive"
    assert result["evaluation"]["hw_mae"] is None
    assert "could not be fitted" in result["evaluation"]["note"]
    assert np.isfinite(result["forecast"].to_numpy()).all()


def test_seasonal_flag_reflects_zero_months_and_selected_method():
    result = ai.forecast_revenue(monthly_rows([100, 0, 90, 120, 140, 150] * 5))
    assert not result["seasonal"]


def test_partial_end_month_is_excluded_without_discarding_first_observation():
    frame = monthly_rows(np.arange(1, 11) * 100)
    frame.loc[len(frame) - 1, "date"] = pd.Timestamp("2023-10-15")
    result = ai.forecast_revenue(frame)
    assert result["partial_month_excluded"]
    assert result["first_month_may_be_partial"]
    assert len(result["history"]) == 9
    assert result["history"].index[-1] == pd.Timestamp("2023-09-01")


@pytest.mark.parametrize("horizon", [0, -1, 1.5, True])
def test_invalid_horizon_is_rejected(horizon):
    with pytest.raises(ValueError, match="positive integer"):
        ai.forecast_revenue(monthly_rows([100] * 12), horizon)


@pytest.mark.parametrize("bad", [np.inf, -1])
def test_unsupported_revenue_is_rejected(bad):
    with pytest.raises(ValueError, match="nonnegative"):
        ai.forecast_revenue(monthly_rows([100] * 11 + [bad]))
