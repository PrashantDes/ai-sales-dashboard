"""Regenerate the synthetic portfolio case study and analytical SVG preview.

Run from the repository root: python scripts/build_case_study.py
No APIs, credentials, network, or third-party datasets are used.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sales_ai.data import END_DATE, START_DATE, generate_sales_data  # noqa: E402
from sales_ai.decisions import decision_brief  # noqa: E402
from sales_ai.ai import forecast_revenue  # noqa: E402


def preview_svg(current: pd.DataFrame, metrics: dict, period: str) -> str:
    """An actual-data chart preview, explicitly distinct from an app screenshot."""
    weekly = current.set_index("date")["revenue"].resample("W").sum()
    low, high = 0.0, max(float(weekly.max()), 1.0)
    points = " ".join(
        f"{76 + i / max(len(weekly) - 1, 1) * 996:.1f},{408 - (float(value) - low) / (high - low) * 128:.1f}"
        for i, value in enumerate(weekly)
    )
    first, last = weekly.index.min().strftime("%d %b"), weekly.index.max().strftime("%d %b")
    cards = [("Revenue", f"INR {metrics['revenue'] / 1e7:.2f} Cr"),
             ("Recorded profit margin", f"{metrics['margin_pct']:.1f}%"),
             ("Orders", f"{metrics['orders']:,}")]
    tiles = []
    for i, (label, value) in enumerate(cards):
        x = 48 + i * 358
        tiles.append(f'<rect x="{x}" y="107" width="336" height="91" rx="12" fill="#fff" stroke="#cbd5e1"/>'
                     f'<text x="{x + 20}" y="135" font-size="14" fill="#475569">{escape(label)}</text>'
                     f'<text x="{x + 20}" y="172" font-size="28" font-weight="700">{escape(value)}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 485" role="img" aria-labelledby="title desc">
<title id="title">Synthetic demo — generated analytics preview</title>
<desc id="desc">Computed sales metrics and weekly revenue for {escape(period)}. This is an analytical preview, not an application screenshot.</desc>
<rect width="1120" height="485" rx="16" fill="#f8fafc"/>
<g font-family="Arial, sans-serif" fill="#0f172a">
<text x="48" y="42" font-size="24" font-weight="700">Sales intelligence · synthetic demo</text>
<text x="48" y="72" font-size="14" fill="#475569">Generated analytics preview · {escape(period)} · seed 42</text>
{''.join(tiles)}
<text x="48" y="227" font-size="17" font-weight="700">Weekly revenue (INR)</text>
<text x="48" y="249" font-size="12" fill="#64748b">First and last buckets may contain partial weeks</text>
<line x1="76" y1="408" x2="1072" y2="408" stroke="#cbd5e1"/>
<line x1="76" y1="280" x2="1072" y2="280" stroke="#e2e8f0"/>
<text x="20" y="284" font-size="11" fill="#64748b">{high / 1e6:.1f}M</text>
<text x="48" y="412" font-size="11" fill="#64748b">0</text>
<polyline points="{points}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linejoin="round"/>
<text x="76" y="432" font-size="12" fill="#64748b">{first}</text>
<text x="1026" y="432" font-size="12" fill="#64748b">{last}</text>
<text x="48" y="464" font-size="12" fill="#475569">Illustrative generated business · no customer data · no measured business impact claimed</text>
</g></svg>
'''


def build_case_study(output_dir: Path = ROOT / "docs") -> dict:
    data = generate_sales_data(seed=42, start=START_DATE, end=END_DATE)
    end = data["date"].max().normalize()
    start = end - pd.Timedelta(days=89)
    previous_start = start - pd.Timedelta(days=90)
    current = data[data["date"].between(start, end)]
    previous = data[data["date"].between(previous_start, start - pd.Timedelta(days=1))]
    brief = decision_brief(current, previous)
    revenue = float(current["revenue"].sum())
    prior_revenue = float(previous["revenue"].sum())
    profit = float(current["profit"].sum())
    metrics = {"revenue": revenue, "profit": profit, "margin_pct": profit / revenue * 100,
               "orders": int(current["order_id"].nunique()), "lines": len(current),
               "previous_revenue": prior_revenue, "revenue_change_pct": (revenue / prior_revenue - 1) * 100}
    forecast = forecast_revenue(data)
    evaluation = forecast["evaluation"]
    holdout = forecast["holdout"]
    forecast_evidence = {
        "method": forecast["method_label"], "history_months": len(forecast["history"]),
        "evaluation": evaluation,
        "holdout": [{"month": f"{month:%Y-%m}", **{key: float(value) for key, value in row.items()}}
                    for month, row in holdout.iterrows()],
    }
    period = f"{start:%d %b %Y} to {end:%d %b %Y}"
    payload = {"data_kind": "synthetic", "seed": 42, "generator_start": START_DATE, "generator_end": END_DATE,
               "current_start": f"{start:%Y-%m-%d}", "current_end": f"{end:%Y-%m-%d}",
               "previous_start": f"{previous_start:%Y-%m-%d}", "previous_end": f"{start - pd.Timedelta(days=1):%Y-%m-%d}",
               "metrics": metrics, "decision_brief": brief, "forecast_evidence": forecast_evidence}
    sections = []
    for finding in brief["findings"]:
        sections.append(f"### {finding['title']}\n\n**Evidence:** {finding['evidence']}\n\n"
                        f"**Next action:** {finding['action']}\n\n**Limit:** {finding['caveat']}")
    forecast_table = "\n".join(
        f"| {month:%b %Y} | {row['actual']:,.0f} | {row['holt_winters']:,.0f} | {row['baseline']:,.0f} |"
        for month, row in holdout.iterrows()
    )
    markdown = f'''# Case study: where should a sales manager investigate first?

This is a reproducible **synthetic demonstration**, not a client engagement or a measured improvement in a real business. It uses the dashboard's Indian D2C generator (seed 42), including its designed seasonality, growth, and unusual days.

## Business question

Revenue is changing and promotions may be putting pressure on margin. Which regions and product lines deserve investigation before the next stock and promotion decisions?

## Scope and preparation

- Current window: **{period}** (90 calendar days).
- Comparison: **{previous_start:%d %b %Y} to {start - pd.Timedelta(days=1):%d %b %Y}** (90 calendar days), with the same dimension scope.
- Full generated history: {START_DATE} to {END_DATE}; currency INR; no dimension filters.
- {metrics['lines']:,} selected order lines and {metrics['orders']:,} distinct orders. The generator uses one line per order, so these counts coincide in this case; uploaded datasets may contain multiple lines per order.
- Revenue and cost are generated and rounded to two decimals; recorded profit is revenue minus cost. Region/product sums reconcile to the selected totals. The synthetic input has no missing cells. This report does not measure performance on real exports.

## Evidence

| Metric | Selected window |
| --- | ---: |
| Revenue | INR {revenue:,.2f} |
| Recorded profit | INR {profit:,.2f} |
| Blended recorded margin | {metrics['margin_pct']:.2f}% |
| Revenue change vs previous 90 days | {metrics['revenue_change_pct']:+.2f}% |

{chr(10).join(chr(10) + section + chr(10) for section in sections)}

## Does the forecast beat a simple baseline?

The full generated history supplies {len(forecast['history'])} usable monthly totals; the trailing incomplete month is excluded by the app's coverage heuristic. The final three usable months ({holdout.index.min():%b %Y} to {holdout.index.max():%b %Y}) are held out chronologically. Both methods train only on the preceding {evaluation['training_months']} months before predicting those observations.

| Method | Validation WAPE | Validation MAE (INR) |
| --- | ---: | ---: |
| Damped-trend Holt-Winters | {evaluation['hw_wape'] * 100:.2f}% | {evaluation['hw_mae']:,.0f} |
| {evaluation['baseline_label']} | {evaluation['baseline_wape'] * 100:.2f}% | {evaluation['baseline_mae']:,.0f} |

| Validation month | Actual (INR) | Holt-Winters (INR) | Baseline (INR) |
| --- | ---: | ---: | ---: |
{forecast_table}

The selected future-forecast method is **{forecast['method_label']}**. WAPE is the sum of absolute errors divided by the sum of actual revenue; MAE is average absolute error in currency units. The method with lower validation MAE is selected and refitted on usable history. These three months are used for model selection, so these scores are **not an independent test estimate**. A real deployment should add rolling-origin evaluation and a later untouched test period before setting commitments. Synthetic seasonal patterns may favour the chosen model.

## Decision and validation plan

Use these findings as an investigation queue. Reconcile source orders and costs before acting; compare like-for-like product and customer groups; review stock constraints; and test promotion changes against a control group. Do not treat a revenue movement as attribution or negative-line losses as recoverable savings.

Success would be assessed through a predeclared pilot metric such as contribution profit per eligible order, with revenue, conversion, and stock availability as guardrails. This project has not run that pilot and claims no realised profit uplift.

## Limits

- Synthetic patterns make the arithmetic reproducible but do not validate generalisation to a real company.
- Adjacent equal-length windows are descriptive comparisons, not seasonally adjusted estimates. The selected period includes a festive-season transition.
- Recorded profit omits expenses that are absent from the input, such as overhead, acquisition, fulfilment, and returns.
- Discount groups have different mixes; their blended margins are an association, not a causal estimate.
- Forecasting and anomaly detection are separate aids for planning and investigation; neither establishes why a movement happened. See the app's forecast holdout comparison before using its projections.

## Reproduce

From the repository root:

```powershell
python scripts/build_case_study.py
python -m pytest
python -m streamlit run app.py
```

The script regenerates this report, [machine-readable metrics](case-study.json), and [the analytical preview](demo-preview.svg) entirely locally. Select generated sample data in the dashboard and the current date window above to inspect the same evidence. The preview is a generated chart, not an application screenshot.
'''
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "case-study.md").write_text(markdown, encoding="utf-8")
    (output_dir / "case-study.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    (output_dir / "demo-preview.svg").write_text(preview_svg(current, metrics, period), encoding="utf-8")
    return payload


if __name__ == "__main__":
    result = build_case_study()
    print(f"Generated docs/case-study.md, docs/case-study.json, docs/demo-preview.svg for {result['current_start']} to {result['current_end']}.")
