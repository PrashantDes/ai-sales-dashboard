# Case study: where should a sales manager investigate first?

This is a reproducible **synthetic demonstration**, not a client engagement or a measured improvement in a real business. It uses the dashboard's Indian D2C generator (seed 42), including its designed seasonality, growth, and unusual days.

## Business question

Revenue is changing and promotions may be putting pressure on margin. Which regions and product lines deserve investigation before the next stock and promotion decisions?

## Scope and preparation

- Current window: **28 Jul 2026 to 25 Oct 2026** (90 calendar days).
- Comparison: **29 Apr 2026 to 27 Jul 2026** (90 calendar days), with the same dimension scope.
- Full generated history: 2023-01-01 to 2026-10-25; currency INR; no dimension filters.
- 7,151 selected order lines and 7,151 distinct orders. The generator uses one line per order, so these counts coincide in this case; uploaded datasets may contain multiple lines per order.
- Revenue and cost are generated and rounded to two decimals; recorded profit is revenue minus cost. Region/product sums reconcile to the selected totals. The synthetic input has no missing cells. This report does not measure performance on real exports.

## Evidence

| Metric | Selected window |
| --- | ---: |
| Revenue | INR 91,606,978.18 |
| Recorded profit | INR 21,945,383.77 |
| Blended recorded margin | 23.96% |
| Revenue change vs previous 90 days | +28.80% |


### Review South: largest regional revenue movement

**Evidence:** South moved from ₹19,084,315 to ₹25,458,959 (₹6,374,645 increase). Total revenue changed by ₹20,482,433.

**Next action:** Compare order volume, product mix, and promotions in this region before changing budget or stock allocation.

**Limit:** This locates the movement; it does not explain its cause. The comparison assumes complete data in equally sized windows and does not adjust for seasonality.


### Check loss-making lines for Smartphone

**Evidence:** 93 loss-making lines generated ₹3,795,434 in revenue and ₹131,155 in gross losses. Smartphone accounts for ₹75,580 of those losses.

**Next action:** Inspect pricing, discounts, and recorded costs for these lines; review exceptions before approving another promotion.

**Limit:** Loss exposure sums negative-profit lines, not net product profit. Some promotions may be intentional. These losses are not a savings estimate.


### Validate the promotion margin tradeoff

**Evidence:** Revenue-weighted margin is 29.3% on 2,448 full-price lines and 20.8% on 4,703 discounted lines (discounted minus full-price: -8.4 percentage points).

**Next action:** Compare like-for-like products and customer groups, then test a promotion with a control group before changing discount policy.

**Limit:** This is an association, not a causal discount effect. Different products, customers, and seasons can explain the gap; volume uplift is not estimated.


## Does the forecast beat a simple baseline?

The full generated history supplies 45 usable monthly totals; the trailing incomplete month is excluded by the app's coverage heuristic. The final three usable months (Jul 2026 to Sep 2026) are held out chronologically. Both methods train only on the preceding 42 months before predicting those observations.

| Method | Validation WAPE | Validation MAE (INR) |
| --- | ---: | ---: |
| Damped-trend Holt-Winters | 4.13% | 1,151,109 |
| Seasonal naive (same month last year) | 18.68% | 5,202,720 |

| Validation month | Actual (INR) | Holt-Winters (INR) | Baseline (INR) |
| --- | ---: | ---: | ---: |
| Jul 2026 | 25,603,294 | 24,428,701 | 20,495,535 |
| Aug 2026 | 28,593,755 | 27,866,024 | 24,022,717 |
| Sep 2026 | 29,351,590 | 27,800,586 | 23,422,226 |

The selected future-forecast method is **Damped-trend Holt-Winters**. WAPE is the sum of absolute errors divided by the sum of actual revenue; MAE is average absolute error in currency units. The method with lower validation MAE is selected and refitted on usable history. These three months are used for model selection, so these scores are **not an independent test estimate**. A real deployment should add rolling-origin evaluation and a later untouched test period before setting commitments. Synthetic seasonal patterns may favour the chosen model.

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
