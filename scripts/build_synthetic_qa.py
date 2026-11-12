"""Build a deterministic upload and independent, penny-exact chart references.

python scripts/build_synthetic_qa.py
Generated files stay local; no credentials, network or real customer data used.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sales_ai.data import generate_sales_data, validate_sales_data  # noqa: E402

SEED = 20261112
START, END = "2023-01-01", "2026-10-25"
EVENTS = {
    "2025-03-12": (4, "Injected promotion demand spike"),
    "2025-06-18": (0.15, "Injected demand drop"),
    "2026-03-18": (4, "Injected promotion demand spike"),
    "2026-08-12": (0.15, "Injected demand drop"),
}
GROUPS = {
    "daily": ["date"], "weekly": ["week_ending_sunday"],
    "monthly": ["month"], "region": ["region"], "city": ["region", "city"],
    "category": ["category"], "product": ["category", "product"],
    "region_category": ["region", "category"],
    "channel_segment": ["channel", "customer_segment"],
    "discount_band": ["discount_band"],
}


def make_data(seed: int = SEED, start: str = START, end: str = END) -> pd.DataFrame:
    """Positive sales lines, exact penny profit and consistent multi-line headers."""
    df = generate_sales_data(seed=seed, start=start, end=end)
    rng = np.random.default_rng(seed + 1)
    # Keep each order on one day with one geography/channel/customer header.
    order_number = 0
    header = ["region", "city", "channel", "customer_segment", "customer_id"]
    header_index = np.arange(len(df))
    order_ids = np.empty(len(df), dtype=object)
    for _, indexes in df.groupby("date", sort=True).groups.items():
        indexes = list(indexes)
        cursor = 0
        while cursor < len(indexes):
            count = min(int(rng.choice([1, 2, 3], p=[0.60, 0.30, 0.10])), len(indexes) - cursor)
            block = indexes[cursor:cursor + count]
            order_number += 1
            order_ids[block] = f"SYN-{order_number:08d}"
            header_index[block] = block[0]
            cursor += count
    df["order_id"] = order_ids
    for column in header:
        df[column] = df[column].to_numpy()[header_index]
    # Cover every dashboard discount band, including a deliberate loss cohort.
    deep = rng.random(len(df)) < 0.035
    old_discount = df.loc[deep, "discount"].to_numpy()
    df.loc[deep, "revenue"] = (df.loc[deep, "revenue"].to_numpy() / (1 - old_discount) * 0.65).round(2)
    df.loc[deep, "discount"] = 0.35
    for when, (factor, _) in EVENTS.items():
        mask = df["date"].eq(pd.Timestamp(when))
        df.loc[mask, ["revenue", "cost"]] = (df.loc[mask, ["revenue", "cost"]] * factor).round(2)
        if factor >= 1:
            df.loc[mask, "units"] *= int(factor)
    # A planted, observable margin pressure cohort; no causal inference implied.
    loss = (df["channel"].eq("Marketplace") & df["product"].eq("Laptop")
            & df["date"].ge("2026-01-01"))
    df.loc[loss, "cost"] = (df.loc[loss, "revenue"] * 1.08).round(2)
    # Calculate profit using integer pennies, then render each amount to 2dp.
    pennies = {c: np.rint(df[c].to_numpy() * 100).astype(np.int64) for c in ("revenue", "cost")}
    df["profit"] = (pennies["revenue"] - pennies["cost"]) / 100
    # A line key prevents genuinely repeated product lines being mistaken for duplicates.
    df.insert(2, "line_id", pd.Series([f"SYN-LINE-{i:09d}" for i in range(1, len(df) + 1)], index=df.index))
    return df


def band(value: str) -> str:
    discount = Decimal(value)
    for limit, label in [("0", "0%"), (".05", "<=5%"), (".10", "<=10%"),
                         (".15", "<=15%"), (".20", "<=20%"), ("1", ">20%")]:
        if discount <= Decimal(limit):
            return label
    raise ValueError("Discount exceeds 100%")


def reference(rows: list[dict], dimensions: list[str] | None = None) -> list[dict]:
    """Independent CSV/Decimal oracle: does not call dashboard aggregations."""
    dimensions = dimensions or []
    groups: dict = {}
    for row in rows:
        day = date.fromisoformat(row["date"])
        extra = {"month": day.strftime("%Y-%m"),
                 "week_ending_sunday": (day + timedelta(days=6-day.weekday())).isoformat(),
                 "discount_band": band(row["discount"])}
        key = tuple(row.get(dim, extra.get(dim)) for dim in dimensions)
        item = groups.setdefault(key, {"revenue_paise": 0, "cost_paise": 0, "profit_paise": 0,
                                       "units": 0, "lines": 0, "orders": set(), "loss_lines": 0})
        for col in ("revenue", "cost", "profit"):
            amount = Decimal(row[col]) * 100
            if amount != amount.to_integral_value():
                raise ValueError("Money must have at most two decimal places")
            item[col + "_paise"] += int(amount)
        item["units"] += int(row["units"])
        item["lines"] += 1
        item["orders"].add(row["order_id"])
        item["loss_lines"] += Decimal(row["profit"]) < 0
    records = []
    for key, value in sorted(groups.items()):
        value = dict(value)
        value["orders"] = len(value["orders"])
        revenue, profit = value["revenue_paise"], value["profit_paise"]
        assert revenue - value["cost_paise"] == profit
        value.update(revenue_inr=f"{Decimal(revenue)/100:.2f}",
                     profit_inr=f"{Decimal(profit)/100:.2f}",
                     margin_pct=float(Decimal(profit) / revenue * 100),
                     aov_inr=float(Decimal(revenue) / 100 / value["orders"]))
        records.append(dict(zip(dimensions, key)) | value)
    return records


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build(output: Path, seed: int = SEED) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    df = make_data(seed)
    upload = output / "synthetic_sales.csv"
    df.to_csv(upload, index=False, date_format="%Y-%m-%d", float_format="%.2f", lineterminator="\n")
    with upload.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    accepted = validate_sales_data(pd.read_csv(upload))
    assert len(accepted) == len(rows) and not accepted.isna().to_numpy().any()
    scenarios = {
        "full_history": (START, END, {}),
        "default_90_days": ("2026-07-28", END, {}),
        "complete_year_2025": ("2025-01-01", "2025-12-31", {}),
        "north_website_2025": ("2025-01-01", "2025-12-31", {"region": "North", "channel": "Website"}),
        "marketplace_electronics_2026": ("2026-01-01", END, {"channel": "Marketplace", "category": "Electronics"}),
        "spike_day": ("2026-03-18", "2026-03-18", {}),
        "partial_october_2026": ("2026-10-01", END, {}),
    }
    evidence: dict[str, dict[str, Any]] = {}
    for name, (start, end, filters) in scenarios.items():
        selected = [r for r in rows if start <= r["date"] <= end and all(r[k] == v for k, v in filters.items())]
        span = date.fromisoformat(end) - date.fromisoformat(start) + timedelta(days=1)
        previous_start = (date.fromisoformat(start) - span).isoformat()
        previous = [r for r in rows if previous_start <= r["date"] < start and all(r[k] == v for k, v in filters.items())]
        totals = reference(selected)[0]
        prior = reference(previous)
        totals_pd = accepted.loc[accepted["date"].between(start, end)]
        for k, v in filters.items():
            totals_pd = totals_pd[totals_pd[k].eq(v)]
        for metric in ("revenue", "cost", "profit"):
            assert round(float(totals_pd[metric].sum()) * 100) == totals[metric + "_paise"]
        assert totals_pd["order_id"].nunique() == totals["orders"]
        folder = output / name
        folder.mkdir(exist_ok=True)
        for chart, dims in GROUPS.items():
            grouped = reference(selected, dims)
            for metric in ("revenue_paise", "cost_paise", "profit_paise", "units", "lines"):
                assert sum(r[metric] for r in grouped) == totals[metric]
            write_csv(folder / (chart + ".csv"), grouped)
        evidence[name] = dict(start_inclusive=start, end_inclusive=end, filters=filters,
                              totals=totals, previous_start=previous_start,
                              previous_end=(date.fromisoformat(start)-timedelta(days=1)).isoformat(),
                              previous_totals=prior[0] if prior else None)
    manifest = dict(schema_version=1, synthetic=True, seed=seed, currency="INR", start=START, end=END,
                    csv_sha256=hashlib.sha256(upload.read_bytes()).hexdigest(),
                    scenarios=evidence, planted_events=EVENTS,
                    validation={"upload_accepted_without_row_loss": True, "independent_totals_match": True,
                                "all_chart_subtotals_reconcile": True},
                    caveats=["Sales lines only; no returns or taxes/shipping ledger.",
                             "Recorded profit is revenue minus included cost, not net company profit.",
                             "Planted events are labels for QA, not guaranteed detector predictions.",
                             "Distinct orders across product/category groups are not additive.",
                             "Forecasts are estimates, not ground truth; use monthly.csv to check history.",
                             "Generator includes additional seeded random anomalies."])
    (output / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    all_totals = evidence["full_history"]["totals"]
    instructions = f"""# Synthetic dashboard QA pack

Entirely fictional Indian ecommerce sales, seed {seed}. Not real business results.

- Upload: `synthetic_sales.csv` (INR), {all_totals['lines']:,} lines, {all_totals['orders']:,} distinct orders.
- Coverage: {START} through {END}; final month intentionally incomplete.
- Exact full-history revenue: INR {all_totals['revenue_inr']}; recorded profit: INR {all_totals['profit_inr']}.

## Open the data

1. Run `python -m streamlit run app.py` from the project root.
2. Choose **Upload my own CSV** in the sidebar and upload `synthetic_sales.csv`.
3. Keep online AI off and use INR. This CSV is for the sales dashboard, not Real-data SQL (GBP).
4. The initial window is the last 90 days. Match `default_90_days` in `expected.json`, not the full-history totals.
5. For each scenario in `expected.json`, set both inclusive dates and its dimension filters; leave other filters at all values.

## Check numbers and graphs

`expected.json` gives exact integer paise, display INR, distinct orders, units, margin, AOV, and equal-length previous-period totals for seven selections. Paise are authoritative; margin and AOV are unrounded ratios. The app rounds cards and abbreviates large amounts.

Each scenario folder has chart reference CSVs: daily, Sunday-ending weekly (partial edges included), monthly, region, city, category, product, region/category, channel/segment, and discount band. Match trend granularity and dates before comparing. For the product bar, sort product revenue descending and use the app's top-N setting. Derive heatmap margin as 100 × profit / revenue, not an average of line margins. `<=` labels correspond to the dashboard's `≤` labels. Revenue/profit subtotals reconcile; distinct order counts across dimensions can overlap.

For Forecast, compare its history to **full dimension-filtered history**, not the active date window. The final partial October is excluded by the app. Predictions and approximate bands are not known future sales. For Anomalies, use daily references and planted dates from `expected.json`; algorithm flags need not match every planted event. For AI Insights in local mode, compare cited values to the same active scenario. Data & EDA should show no missing values or dropped rows.

Multi-line orders share dates, customer, geography, segment and channel. All six discount bands are populated; some sales deliberately lose money. A 2026 Marketplace Laptop cohort has cost above revenue. `marketplace_electronics_2026` includes other Electronics products too; inspect Laptop in its product reference. Demand-drop days scale order values, so do not interpret them as a measured outage mechanism. No invalid rows are mixed into the clean upload.

Regenerate: `python scripts/build_synthetic_qa.py`. All generated pack files are ignored by Git; the generator and instructions can be reviewed separately. Reproducibility is within the installed numerical dependency environment; SHA-256 identifies this exact CSV.
"""
    (output / "README.md").write_text(instructions, encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/synthetic-qa")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    result = build(args.output_dir, args.seed)
    print(json.dumps({"output": str(args.output_dir), "sha256": result["csv_sha256"],
                      "totals": result["scenarios"]["full_history"]["totals"],
                      "validation": result["validation"]}, indent=2))
