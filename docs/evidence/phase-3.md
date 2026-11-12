# Phase 3 evidence ? business SQL and reconciliation

Status: PASS | Date: 2026-11-12, Asia/Kolkata | Branch: feat/retail-sql-investigation

Executor/reviewer: Codex self-review; no external stakeholder approval or remote CI execution claimed. P2 database byte hash still matches its acceptance record. Existing uncommitted work remains uncommitted; no merge, push or UI integration occurred.

## Deliverables

- [SQL query catalogue](../sql-query-catalogue.md): question, named query, output grain, metrics, denominators and limitations.
- Seven named SQL files in `sql/online_retail/`, using CTEs, CASE, LAG, ROW_NUMBER, cumulative window sums and a cardinality-safe invoice lookup join.
- `sales_ai/retail_queries.py`: whitelisted query execution, canonical ISO/exclusive-end parameter validation and an independently calculated Python oracle.
- `scripts/verify_retail_sql.py`: full-data verification; publishes only aggregate validation evidence.
- `tests/test_retail_sql.py`: fixture checks for grain, gaps, partial windows, ties, missing IDs, zero denominators, future dates, malformed inputs and parameter safety.

## Gate results

| Requirement | Actual result |
| --- | --- |
| P3-01 Catalogue | Seven inspectable queries map to all four business questions |
| P3-02 Monthly results | Gross, cancellation, net integer units, distinct invoices and adjacent-month growth reconcile; incomplete December2011 excluded |
| P3-03 Exposure | Product and transaction-country group values and cancellation ratios match independent calculations |
| P3-04 Concentration | Full product/identified-customer populations, deterministic ties, cumulative units and denominator reconcile; no top-N omission |
| P3-05 Purchasing | Distinct-invoice repeat share and observed invoice sequencing reconcile; future observations excluded before sequencing |
| P3-06 Independent checks | Python reads canonical line records and independently groups/sets/sorts them; expected results are not calculated by SQL aggregates |
| P3-07 Fixtures | Calendar gaps do not produce adjacent growth; zero denominators remain null; ratios above100% are retained; lines are not mistaken for distinct invoices; unknown customers are excluded only from customer metrics |
| P3-08 Full dataset | All7 queries pass row-wise reconciliation in4 scopes, including full541,909-row source scope, UK selection, partial terminal month and empty/injection-like country scope |

Monetary integers and distinct counts match exactly. Ratios are dimensionless floating-point values; no tolerance was used to excuse mismatched monetary units. Display currency rounding belongs to the subsequent UI and follows the existing half-even contract. Every group is returned, so country/product subtotals reconcile to the same eligible sales/cancellation population; identified-customer denominators disclose missing-customer coverage separately.

The monthly query conservatively omits the last observed source month and selected-window partial months. Missing calendar months are not bridged by LAG. Purchase sequence groups eligible sales lines to invoices, joins the unique accepted invoice lookup, sequences history strictly before end, and only then restricts displayed purchases to start. The Python oracle does not reproduce that SQL join; it independently calculates invoice sets and timestamps from line records.

## Reproduction

```powershell
.\.venv\Scripts\python.exe scripts/verify_retail_sql.py
.\.venv\Scripts\python.exe -m pytest -o cache_dir=.venv/phase0-runtime/pytest-cache
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Tests use the established host/cache/temp context to avoid the documented filesystem-sandbox cleanup permissions. No tests are skipped and warnings are not suppressed.

Evidence: [aggregate full-data reconciliation](phase-3/reconciliation.json), [final tests](phase-3/tests.txt), [hashes and checks](phase-3/checks.json). Actual source identifiers and purchase-sequence rows are not written into the published evidence. Source data and SQLite remain ignored by Git.

## Limitations and decision

Results follow contract1.0 classifications, including retained duplicate-looking rows and conservative nonmerchandise exclusions. Cancellation exposure is not a verified return rate; repeat share is within-window observed purchasing, not lifetime retention. Product descriptions are not attached to rankings here, so no future-looking description is introduced. No cost/profit, causal effect, realised business uplift, final narrative recommendation or production readiness is asserted.

All eight P3 tasks and required analytical checks pass. Unexplained discrepancies:0. Final complete regression suite: **122 passed in33.08seconds, zero warnings, exit0**. Dependency consistency and whitespace checks pass. P3 PASS; P4 READY, not started. Query outputs must still be integrated and tested in the UI under P4 before being represented as an accepted real-data application view.
