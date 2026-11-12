# Synthetic dataset for dashboard checks

Generate an entirely fictional, deterministic sales upload and penny-exact reference tables:

```powershell
.\.venv\Scripts\python.exe scripts/build_synthetic_qa.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open **Upload my own CSV** and upload `data/synthetic-qa/synthetic_sales.csv`. Keep online AI off. This pack targets the standard INR sales dashboard; it does not replace the accepted historical GBP database.

Open `data/synthetic-qa/README.md` for checks, `expected.json` for seven filter selections and their current/previous-period metrics, and each selection's folder for chart reference CSVs. The starting dashboard selection uses the final 90 days; full-history totals require changing dates.

The generator includes nearly four years of seasonality and growth, four regions, 16 cities, 20 products, four channels, three customer segments, multi-line orders, all six discount bands, negative-profit sales, planted demand events and an incomplete final month. Order headers are consistent and each line has a unique synthetic identifier. It uses no personal or real commercial records. Inputs satisfy the app's positive-sales contract; returns are not encoded as negative sales.

Reference tables independently read serialized CSV amounts using Decimal and integer paise, rather than calling dashboard aggregate functions. Each chart partition must reconcile to the scenario totals. Margin and AOV are ratios of totals. Distinct orders across product/category partitions can overlap. The generator verifies upload acceptance without row loss and compares accepted pandas totals with the independent reference.

This is a realistic QA dataset, not certification of production readiness or a benchmark of the deployed service. Forecasts have no known future truth; use the reference monthly history and the app's validation comparison. Anomaly flags need not match every planted event. Reports describe intentional assumptions and partial periods.

Generated artifacts are ignored by Git to avoid repository bulk. The script and regression tests are reviewable; regenerate locally when needed. No app behavior or accepted real-data outputs change.

## Verification of the generated pack

Verified on 2026-11-12 using the local Python 3.12 environment:

- 79,923 lines, 53,746 distinct orders, 141,105 units, including 1,591 negative-profit lines.
- All seven scenario totals match the independently serialized CSV references; all chart partition monetary/unit/line totals reconcile.
- Streamlit AppTest uploaded the actual generated CSV, matched all five headline metrics across all seven selections, and opened all six tabs without an exception. Nine Plotly charts were created across the analytical tabs. This checks app execution, not browser painting or every plotted point.
- The full offline regression suite passed: 132 tests in 21.68 seconds. The initial focused test run had a sandbox cache-write warning; rerunning without the pytest cache and running the full suite with appropriate filesystem permissions passed.
- AppTest emitted its expected bare-mode ScriptRunContext warnings; no dashboard exception occurred. Per-scenario and per-tab results are saved locally as `data/synthetic-qa/app-checks.json`.

CSV SHA-256: `b2db8673e1265188cf6fa5d08e87870eb34c3cb9277ae95d06290244ac77283e`.

Full-history revenue is INR 995,122,164.27; recorded profit INR 231,123,588.77. The initial 90-day view instead has revenue INR 91,881,574.71 and recorded profit INR 20,328,654.21. The reference manifest contains the remaining exact metrics and denominators. Production numeric calculations use floating-point arithmetic; references use integer paise.
