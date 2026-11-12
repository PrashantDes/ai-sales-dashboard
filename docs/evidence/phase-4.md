# Phase 4 evidence ? real-data SQL view

Status: PASS | Date: 2026-11-12, Asia/Kolkata | Branch: feat/retail-sql-investigation

Implementation and automated verification: Codex. Visual review: **user**, who replied ?Reviewed?looks correct? after being asked to inspect the running real-data view's four sections, quality/SQL expanders, charts, labels, tables and metric clipping. No independent external reviewer, browser screenshot, remote CI or deployment is claimed.

## Deliverables and navigation

Select **Real-data SQL (GBP)** in the sidebar. `sales_ai/retail_view.py` renders the dedicated view and `app.py` dispatches before the synthetic/custom dashboard schema and optional AI controls. The view has no provider calls, fabricated cost/profit fields, raw transaction table, or automatic source download.

The four sections show complete-month trends, product/country cancellation exposure, sales concentration, and repeat purchasing/identification coverage. Definitions, historical coverage, active dates/country, GBP/monetary units, whole-workbook quality counts, source hash/policy, accepted SQL and parameters are visible. Aggregate downloads explicitly omit customer rankings and purchase sequences.

## Required checks

| Task/check | Actual result |
| --- | --- |
| P4-01 Separate source mode | Real-data path exits before existing profit schema; original generated/upload flows still pass |
| P4-02 Scope and definitions | Historical2010-2011 dates, GBP, inclusive selected dates/exclusive SQL end, country, coverage and noncausal limits shown |
| P4-03 Four analysis groups | Rendered from six accepted aggregate queries; seventh purchase-sequence SQL is inspectable but not executed/exposed as individual records in the UI |
| P4-04 Downloads | Actual downloaded JSON matches active filters and accepted summary; no customer/invoice identifiers or customer-rank/sequence rows |
| P4-05 Invalid/empty states | Missing/corrupt/unsupported DB, incomplete dates, empty scope, cancellation-only/zero-sales scope and absent identified purchasers tested without crashes or substituted sample metrics |
| P4-06 State/cache | Retail dates/country and original dashboard dates/region/tab survive source switches; file identity/size/mtime/ctime invalidate cached data after rebuild |
| P4-07 Tests/offline | Five new AppTest cases and full existing suite pass; provider calls are forbidden in new UI fixtures |
| Headline reconciliation | Running actual-source view matched accepted SQL in full-source, UK-filtered and partial-December scopes |
| Partial months | Complete-month message shown for December2011 selection; other summaries explicitly retain selected partial-window values |
| Privacy | Customer IDs removed before presentation cache; JSON export allowlist excludes customer concentration and purchase sequencing |
| Visual review | User reviewed actual running app and confirmed readability/no clipping |
| Final regression suite | **127 passed in33.62seconds, zero warnings, exit0** |
| Static/dependency checks | ty check passed for edited app/view/UI test files; pip check clean; git diff --check clean |
| Upstream consistency | Phase3 SQL/source hashes and accepted database byte hash unchanged |

## Running app verification

The temporary server ran on `127.0.0.1:8765` with the Streamlit1.67 agent API and usage statistics disabled. Its OpenAPI protocol was read before interaction. Actual metrics checked against accepted read-only SQL included full-source gross GBP10,271,433.06, cancellation exposure GBP478,724.18 and net merchandise value GBP9,792,708.88. These are recorded merchandise values under the contract, not profit.

The API verified three scopes, fetched the actual aggregate download URL and checked its contents, switched between original and real-data modes, verified filter persistence, and checked the partial-month message. The final code rerun returned `ready`; the server console emitted no warnings/traceback. The agent API provides semantic checks, not a visual screenshot. Browser/computer tooling was unavailable; the separate visual requirement was satisfied by the user's explicit review, not inferred from automated tests or elapsed time.

After that review and final checks, the temporary server was stopped. Run `python -m streamlit run app.py` normally to use the view again.

## Commands and evidence

```powershell
.\.venv\Scripts\python.exe -m pytest -o cache_dir=.venv/phase0-runtime/pytest-cache
.\.venv\Scripts\python.exe -m ty check app.py sales_ai/retail_view.py tests/test_retail_app.py --output-format concise
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Tests use the documented host/cache/temp context to avoid restricted filesystem cleanup permissions. No warning filters or test skips were introduced.

- [Final test transcript](phase-4/tests.txt).
- [Running app, download and user-review evidence](phase-4/live-app.json).
- [Final hashes and check results](phase-4/checks.json).

## Issues found and resolved

Type checking exposed nullable widget/pandas-date ambiguity, including pre-existing diagnostics in the edited entry point. Widget selections are explicitly narrowed and date boundaries use Python date values; edited files now pass ty.

Preserving original dashboard state initially used a changing tab default, which reset tabs and failed two existing regressions. The [failed run](phase-4/tab-state-failure.txt) is retained. Tab identity now has a stable default, with backed-up selection restored only when its widget state is absent. Date/dimension settings are separately backed up per source. The final127-test run covers original tab navigation and source-switch restoration.

## Limits and gate decision

Native Streamlit chart/table layout was reviewed by the user; no pixel-level automated browser test is claimed. Grouped business data can still be sensitive: removing customer identifiers does not establish anonymisation. Database read-only access is local, not a multi-user access-control system. Performance targets and clean-install release checks remain P6 work. The new view deliberately leaves AI, cost/profit inference and business-impact claims out.

All seven P4 tasks and required checks pass, including the separately confirmed visual review. Blocking issues:0. **P4 PASS; P5 READY, not started.** Changes remain uncommitted. No final real-data narrative case study or deployment has begun.
