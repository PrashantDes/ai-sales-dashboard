"""Boundary and quality checks for uploaded order-line data."""
import numpy as np
import pandas as pd
import pytest

from sales_ai.data import generate_sales_data, validate_sales_data
from sales_ai.cleaning import clean_superstore
from tests.fake_superstore import make_fake_superstore


def order(**changes):
    row = dict(date="2026-01-31", order_id="A", region="North", city="Delhi",
               category="Office", product="Desk", channel="Web", customer_segment="Consumer",
               units=1, revenue=100, cost=60, discount=0)
    return {**row, **changes}


@pytest.mark.parametrize("field,value", [("revenue", np.inf), ("cost", -np.inf),
    ("discount", np.inf), ("discount", -0.1), ("discount", 101),
    ("units", 0), ("units", 1.5), ("revenue", 0), ("cost", -1)])
def test_invalid_numeric_values_rejected(field, value):
    with pytest.raises(ValueError):
        validate_sales_data(pd.DataFrame([order(**{field: value})]))


def test_percentage_column_scaled_but_mixed_scale_rejected():
    clean = validate_sales_data(pd.DataFrame([order(discount=10), order(discount=20)]))
    assert clean.discount.tolist() == [0.1, 0.2]
    with pytest.raises(ValueError, match="mixes"):
        validate_sales_data(pd.DataFrame([order(discount=0.2), order(discount=10)]))


def test_missing_dimensions_preserve_group_totals_and_record_audit():
    clean = validate_sales_data(pd.DataFrame([order(region=None, category="  ")]))
    assert clean.region.iloc[0] == clean.category.iloc[0] == "Unknown"
    assert clean.groupby("region").revenue.sum().sum() == clean.revenue.sum()
    assert any(row["Step"].startswith("Missing dimension") and row["Result"] == "2"
               for row in clean.attrs["cleaning_report"])


@pytest.mark.parametrize("identifier", [None, "", "   "])
def test_order_id_required(identifier):
    with pytest.raises(ValueError, match="Order ID"):
        validate_sales_data(pd.DataFrame([order(order_id=identifier)]))


def test_inconsistent_profit_is_explained():
    with pytest.raises(ValueError, match="Profit must equal"):
        validate_sales_data(pd.DataFrame([order(profit=50)]))


def test_dropped_rows_have_audit_and_mixed_dates_are_retained():
    clean = validate_sales_data(pd.DataFrame([order(date="2026-01-31"),
        order(date="02/01/2026"), order(date="invalid")]))
    assert len(clean) == 2
    assert any(row["Result"] == "1" and "dropped" in row["Step"]
               for row in clean.attrs["cleaning_report"])


@pytest.mark.parametrize("days", [1, 5, 65, 70])
def test_short_generator_ranges(days):
    start = pd.Timestamp("2026-01-01")
    frame = generate_sales_data(start=str(start.date()), end=str((start + pd.Timedelta(days=days - 1)).date()))
    assert not frame.empty
    assert frame.date.min() >= start
    assert frame.date.max() < start + pd.Timedelta(days=days)


def test_reversed_generator_dates_have_clear_error():
    with pytest.raises(ValueError, match="Start date"):
        generate_sales_data(start="2026-02-01", end="2026-01-01")


@pytest.mark.parametrize("field,value", [("Sales", 0), ("Order Date", "invalid"),
    ("Profit", np.inf), ("Order ID", ""), ("Quantity", 0)])
def test_superstore_no_valid_rows_is_actionable(field, value):
    raw = make_fake_superstore(2)
    raw[field] = value
    with pytest.raises(ValueError, match="No valid Superstore"):
        clean_superstore(raw)


def test_superstore_missing_labels_and_nonfinite_rows_are_audited():
    raw = make_fake_superstore(3).iloc[:3].copy()
    raw.loc[0, "Region"] = "  "
    raw.loc[1, "Sales"] = np.inf
    clean, report = clean_superstore(raw)
    assert len(clean) == 2
    assert "Unknown" in clean.region.tolist()
    assert any("non-finite" in step for step in report.Step)
