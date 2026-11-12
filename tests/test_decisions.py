import pandas as pd
import pytest

from sales_ai.decisions import decision_brief


def frame(rows):
    return pd.DataFrame(rows, columns=["region", "product", "revenue", "profit", "discount"])


def test_region_driver_reconciles_without_dividing_by_small_prior_sales():
    current = frame([("West", "A", 300, 80, 0), ("East", "B", 100, 10, .2)])
    previous = frame([("West", "A", 100, 20, 0), ("South", "C", 50, 5, 0)])
    brief = decision_brief(current, previous, "$")
    drivers = brief["region_drivers"]
    assert drivers[0]["region"] == "West"
    assert drivers[0]["change"] == 200
    assert sum(row["change"] for row in drivers) == 250
    assert brief["findings"][0]["metrics"]["total_revenue_change"] == 250
    assert "does not explain its cause" in brief["findings"][0]["caveat"]


def test_loss_exposure_counts_negative_lines_not_net_product_profit():
    current = frame([("West", "A", 100, -20, .2), ("West", "A", 200, 80, 0), ("East", "B", 50, -10, .1)])
    brief = decision_brief(current, current.iloc[:0])
    exposure = brief["loss_exposure"]
    assert exposure["loss_amount"] == 30
    assert exposure["loss_line_count"] == 2
    assert exposure["loss_line_revenue"] == 150
    assert exposure["product"] == "A"
    assert exposure["product_loss"] == 20
    finding = next(f for f in brief["findings"] if f["id"] == "loss_exposure")
    assert "not net product profit" in finding["caveat"]
    assert "not a savings estimate" in finding["caveat"]


def test_discount_comparison_uses_blended_margins_and_never_assumes_erosion():
    current = frame([("West", "A", 100, 10, 0), ("West", "B", 900, 180, 0), ("East", "C", 100, 50, .2)])
    brief = decision_brief(current, current.iloc[:0])
    comparison = brief["discount_comparison"]
    assert comparison["full_price_margin_pct"] == pytest.approx(19)
    assert comparison["discounted_margin_pct"] == 50
    assert comparison["gap_pts"] == pytest.approx(31)
    finding = next(f for f in brief["findings"] if f["id"] == "discount_association")
    assert "not a causal discount effect" in finding["caveat"]
    assert "compress" not in finding["evidence"]


def test_no_previous_rows_does_not_claim_zero_previous_sales():
    current = frame([("West", "A", 100, 10, 0)])
    brief = decision_brief(current, current.iloc[:0])
    assert not brief["comparison_available"]
    assert brief["region_drivers"] == []
    assert all(f["id"] != "revenue_driver" for f in brief["findings"])
    assert brief["discount_comparison"] == {}


def test_empty_selection_has_no_findings():
    empty = frame([])
    assert decision_brief(empty, empty)["findings"] == []
