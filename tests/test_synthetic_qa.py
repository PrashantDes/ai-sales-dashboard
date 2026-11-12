"""Independent money/count checks for the synthetic upload QA generator."""
import csv
from io import StringIO

import pandas as pd
import pytest

from scripts.build_synthetic_qa import make_data, reference
from sales_ai.data import validate_sales_data


def test_reference_keeps_pennies_and_distinct_multiline_orders():
    rows = [dict(date="2026-03-01", order_id="A", region="North", units="2",
                 discount="0.00", revenue="0.10", cost="0.07", profit="0.03"),
            dict(date="2026-03-01", order_id="A", region="South", units="1",
                 discount="0.35", revenue="0.20", cost="0.25", profit="-0.05")]
    totals = reference(rows)[0]
    assert totals["revenue_paise"] == 30
    assert totals["profit_paise"] == -2
    assert totals["orders"] == 1 and totals["lines"] == 2
    assert totals["aov_inr"] == pytest.approx(0.3)
    assert totals["margin_pct"] == pytest.approx(-100 / 15)
    assert totals["loss_lines"] == 1
    assert sum(r["orders"] for r in reference(rows, ["region"])) == 2
    assert reference(rows, ["week_ending_sunday"])[0]["week_ending_sunday"] == "2026-03-01"


def test_generated_upload_is_deterministic_and_order_headers_consistent():
    a = make_data(seed=18, start="2026-01-01", end="2026-01-31")
    b = make_data(seed=18, start="2026-01-01", end="2026-01-31")
    pd.testing.assert_frame_equal(a, b)
    data = validate_sales_data(pd.read_csv(StringIO(a.to_csv(index=False, float_format="%.2f"))))
    assert len(data) == len(a)
    assert data["order_id"].nunique() < len(data)
    assert data["line_id"].is_unique
    for col in ("date", "region", "city", "channel", "customer_segment", "customer_id"):
        assert data.groupby("order_id")[col].nunique().eq(1).all()
    rows = list(csv.DictReader(StringIO(a.to_csv(index=False, date_format="%Y-%m-%d", float_format="%.2f"))))
    assert reference(rows)[0]["revenue_paise"] == round(data["revenue"].sum() * 100)


def test_reference_discount_edges_and_sunday_buckets():
    rows = [dict(date="2026-03-02", order_id=str(i), units="1", discount=d,
                 revenue="1.00", cost="1.00", profit="0.00")
            for i, d in enumerate(["0", "0.05", "0.10", "0.15", "0.20", "0.35"])]
    assert {r["discount_band"] for r in reference(rows, ["discount_band"])} == {"0%", "<=5%", "<=10%", "<=15%", "<=20%", ">20%"}
    assert reference(rows, ["week_ending_sunday"])[0]["week_ending_sunday"] == "2026-03-08"
