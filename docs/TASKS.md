# Phased implementation tasks and acceptance gates

Version: 1.0 | Date: 2026-11-12

Requirements: [PRD](PRD.md). Boundaries and planned paths: [Scope](SCOPE.md).

## How to use this checklist

1. Work only on the current eligible phase. Complete its required tasks before running its exit checks.
2. Run the checks against the actual working files and environment. Record failures and fixes; do not copy an old passing result.
3. Save an evidence record at `docs/evidence/phase-N.md` with commands, results, versions, and artifact links. Never include keys or row-level customer identifiers.
4. Mark the gate `PASS` only when every required check passes and no blocking issue remains. Then unlock the next phase.
5. If upstream data, schema, policy, or code changes affect an accepted result, mark the affected gate and downstream gates `RECHECK REQUIRED` and rerun relevant checks before advancing.

These gates are a workflow specification, not an implemented enforcement script. This documentation task does not run or pass implementation phases. No extra user permission is required for routine implementation/testing already within the authorised scope.

## Status board

| Phase | Status | Evidence | Next action |
| --- | --- | --- | --- |
| P0 Baseline | PASS | [Phase 0 evidence](evidence/phase-0.md) | Baseline verified on 2026-11-12 |
| P1 Source and contract | PASS | [Phase 1 evidence](evidence/phase-1.md) | Source profiled; contract v1.0 frozen |
| P2 Preparation/database | PASS | [Phase 2 evidence](evidence/phase-2.md) | Database prepared and reconciled |
| P3 SQL/reconciliation | PASS | [Phase 3 evidence](evidence/phase-3.md) | Named SQL reconciled on fixtures and real data |
| P4 UI integration | PASS | [Phase 4 evidence](evidence/phase-4.md) | UI verified; visual review confirmed by user |
| P5 Case study | PASS | [Phase 5 evidence](evidence/phase-5.md) | Real-data report regenerated and verified |
| P6 Release verification | BLOCKED | [Phase 6 evidence](evidence/phase-6.md) | Local checks pass; required GitHub Actions jobs pending |

Allowed gate states: `READY`, `IN PROGRESS`, `BLOCKED`, `FAIL`, `PASS`, `RECHECK REQUIRED`. Blocked here means a phase dependency, not a finding that the existing dashboard is broken.

## P0 — Verify the existing baseline

Entry: planning files reviewed for consistency. No new dataset or product feature required.

- [x] P0-01 Record current Git branch/status and preserve existing unrelated changes; establish the implementation branch without staging secrets or local data.
- [x] P0-02 Verify the project `.venv` interpreter, supported Python version, runtime dependencies, and development dependencies.
- [x] P0-03 Run the existing regression suite and record the actual count/outcome in this environment.
- [x] P0-04 Regenerate the existing synthetic case study and verify its expected artifacts and valid JSON/SVG.
- [x] P0-05 Check the existing local demo: overview, forecast, anomalies, AI/local mode, custom uploads, and cleaning report.
- [x] P0-06 Record existing failures/warnings and their disposition; distinguish sandbox/tooling cleanup warnings from application failures.

Checks (PowerShell, repository root):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/build_case_study.py
git diff --check
```

Exit gate: all existing tests pass, dependency consistency passes, generated artifacts parse, no existing application crash is left unresolved, and `docs/evidence/phase-0.md` records the baseline. A previous report of 114 tests is historical context, not this gate's evidence.

**Stop:** do not acquire or integrate the new source until P0 is PASS.

## P1 — Acquire, profile, and freeze the data contract

Entry: P0 PASS. Addresses FR-02 and establishes the definitions needed for FR-03–FR-07.

- [x] P1-01 Record official UCI source attribution, DOI, licence, and historical scope in `docs/retail-provenance.md`.
- [x] P1-02 Add source/raw/database ignore rules before placing files in the repository tree.
- [x] P1-03 Declare the workbook reader dependency and a reproducible download/import command. Use timeouts, error checks, and safe handling of the expected workbook/archive.
- [x] P1-04 Download/import the actual source and create a manifest with SHA-256, worksheet, row count, date bounds, and tool versions.
- [x] P1-05 Profile missing values, invalid dates, numeric precision/ranges, duplicate-looking rows, invoice header conflicts, cancellation prefixes/signs, missing customer IDs, product descriptions, and non-merchandise codes.
- [x] P1-06 Freeze `docs/retail-data-contract.md`: line/invoice/customer grain, classification rules, duplicate policy, financial precision, metric formulas/denominators, date completeness, and population coverage.
- [x] P1-07 Create small synthetic fixtures covering both ordinary and contradictory records; do not publish real customer rows as fixtures.

Required checks:

- [x] Actual input has the required columns and is readable with declared dependencies.
- [x] Source hash and observed bounds/counts are recorded, not inferred from metadata.
- [x] Profile counts can be regenerated from the same file; every treatment decision references a profile observation or explicit assumption.
- [x] The precision policy preserves observed price precision or rejects unsupported precision explicitly; no silent penny rounding.
- [x] Missing-ID and duplicate policies cannot create one fictional customer or silently discard valid repeated lines.
- [x] Cancellation exposure is distinguished from verified returns and matched-purchase return rates.
- [x] `git status`/`git check-ignore` demonstrate that raw files and intended database paths are untracked/ignored.
- [x] Existing tests and `git diff --check` still pass.

Exit gate: source/profile/manifest and a complete versioned data contract exist, all decisions have a rationale, and evidence is recorded in `phase-1.md`.

**Stop:** do not implement final analytical transformations or publish KPI results while treatment rules remain unresolved.

## P2 — Prepare data and build the SQLite model

Entry: P1 PASS. Addresses FR-02–FR-04.

- [x] P2-01 Implement staging import with stable source-row identity, original values, and preparation-policy metadata.
- [x] P2-02 Implement classified analytical lines, including explicit exclusions/quarantine reasons and separate overlapping quality flags.
- [x] P2-03 Implement schema, justified lookup tables/views, constraints, indexes, and documented grain/key relationships.
- [x] P2-04 Implement deterministic rebuilds and safe failed-build behaviour; protect the last valid database.
- [x] P2-05 Generate the quality report and row/value reconciliation, including the effect of the duplicate policy.
- [x] P2-06 Add ingestion and quality tests for invalid/missing fields, signs, source precision, unknown customers, duplicate-looking lines, and invoice conflicts.
- [x] P2-07 Test read-only access and parameterised filter handling for future UI queries.

Required automated checks:

- [x] `PRAGMA integrity_check` reports `ok`; declared foreign-key/uniqueness checks have zero violations.
- [x] Raw row count equals mutually exclusive included + excluded + quarantined counts.
- [x] Every staged row is traceable to a final disposition; flag counts are not incorrectly added together as removed rows.
- [x] Rebuilding the same source/policy yields identical analytical rows and totals, excluding intentionally variable manifest timestamps.
- [x] A forced failed build leaves the previous valid database intact or leaves no database that can be mistaken for valid.
- [x] Missing-ID rows remain eligible for appropriate sales totals but do not form a fake identified customer.
- [x] Joining each lookup preserves eligible line counts and monetary sums.
- [x] New ingestion/quality tests and the existing regression suite pass.

Full-data checks: run preparation on the actual downloaded workbook, inspect the disposition report, and verify all reconciliations. Fixture-only success cannot pass this gate.

Exit gate: a usable local database, preparation command, quality report, and `phase-2.md` evidence exist with no unexplained loss/inflation.

**Stop:** do not build final business queries on an unreconciled database.

## P3 — Implement SQL and independently reconcile findings

Entry: P2 PASS. Addresses FR-05–FR-07.

- [x] P3-01 Create a query catalogue mapping each business question to named `.sql` files, filter parameters, definitions, output grain, and relevant PRD metrics.
- [x] P3-02 Implement complete-month gross sales, cancellation value, recorded net merchandise value, and adjacent-month change using CASE/CTEs/LAG.
- [x] P3-03 Implement product and country cancellation exposure, clearly distinguishing absolute value from cancellation-to-sales ratio.
- [x] P3-04 Implement product and identified-customer concentration with deterministic ranking/ties and correct population denominators.
- [x] P3-05 Implement purchase sequencing and within-window repeat-customer share without line/order double counting or future observations.
- [x] P3-06 Build independent Python reconciliations from the same accepted source classification; do not merely call the SQL result twice.
- [x] P3-07 Add fixture assertions for exact financial units, join inflation, dates/gaps, missing IDs, zero denominators, ties, cancellation signs, and multiple lines per invoice.
- [x] P3-08 Execute the full query suite on real data and save aggregate reconciliation evidence.

Required checks:

- [x] All named queries execute on SQLite and match their catalogue definitions.
- [x] SQL/Python canonical financial units match exactly; displayed-total differences follow the documented rounding rule and do not exceed GBP 0.01.
- [x] Distinct invoice/customer counts match exactly at their defined grains.
- [x] Product/country subtotals reconcile to totals for the same eligible population; top-N outputs disclose omitted groups.
- [x] Full vs partial months and missing comparison months behave as defined; LAG does not disguise a calendar gap.
- [x] No customer purchase after the selected end date influences ranking/sequencing for that selection.
- [x] Cancellation ratios with a zero denominator are unavailable rather than infinity; ratios above 100% are not silently clipped.
- [x] All SQL/reconciliation tests and previous-phase tests pass.

Exit gate: every planned question has reconciled SQL output, query catalogue entries, and `phase-3.md` evidence. No unexplained discrepancy is waived as “close enough.”

**Stop:** do not expose unaccepted SQL results in the application.

## P4 — Integrate the real-data view

Entry: P3 PASS. Addresses FR-01, FR-08, and FR-09.

- [x] P4-01 Add a distinct real-data SQL view; do not map absent costs into the existing profit/margin contract.
- [x] P4-02 Display historical scope, GBP units, source attribution, data-quality coverage, active filters, and metric definitions.
- [x] P4-03 Add the four focused analysis groups and readable SQL/aggregate-table inspection.
- [x] P4-04 Add scoped aggregate downloads without customer identifiers or raw transaction exports.
- [x] P4-05 Implement absent/invalid database, empty filters, zero denominators, no identified customers, and partial-month states.
- [x] P4-06 Preserve filter/tab state, invalidate cached results after a new database build, and keep expensive work off inactive views.
- [x] P4-07 Add Streamlit AppTest flows and verify that neither the existing offline demo nor the new investigation makes provider requests.

Required checks:

- [x] Displayed headline values equal accepted SQL outputs under matching filters.
- [x] Failed/missing real-data input never displays synthetic figures under a real-data label.
- [x] No invented profit, current-business/freshness claim, verified-return claim, or causal recommendation appears.
- [x] Navigation preserves settings; changing dates/source cannot show a stale report for another selection.
- [x] All empty/error states are readable and crash-free.
- [x] Query rendering and charts/tables have readable labels, dates, units, and disclosed denominators.
- [x] Downloads contain intended aggregates/scope only; no raw/customer identifiers or keys are exposed.
- [x] UI tests plus all analytical regression tests pass; manually inspect the rendered view using the actual real-data build.

Exit gate: real-data interface and edge cases pass, existing dashboard remains functional, and `phase-4.md` records automated and manual evidence separately.

**Stop:** do not write final report conclusions from screenshots or an unreconciled/stale selection.

## P5 — Build the real-data case study and portfolio evidence

Entry: P4 PASS. Addresses FR-10.

- [x] P5-01 Generate `docs/sql-case-study.md` and aggregate evidence from the accepted SQL queries and a fixed documented selection.
- [x] P5-02 Write three findings, each with figures, a proposed investigation, an explicit limitation, and a link to the relevant query.
- [x] P5-03 Explain the most important cleaning judgments and show their effect on the eligible population.
- [x] P5-04 Add actual charts or a redacted real-data UI preview with accurate captions; do not manufacture a screenshot or business outcome.
- [x] P5-05 Update README setup, SQL walkthrough, source attribution, reproduction commands, limitations, and the distinction between synthetic and real cases.
- [x] P5-06 Regenerate the report from scratch and compare deterministic contents; document any intentional timestamp/version differences.
- [x] P5-07 Review claims and exports for causality overreach, fabricated costs/impact, identifying data, secrets, and unsupported generalisation.

Required checks:

- [x] Every headline figure and chart can be traced to a query/output for the stated source hash, policy version, and filter scope.
- [x] Narrative, charts, SQL outputs, and independently reconciled totals agree.
- [x] Recommendations follow the evidence and are labelled proposed actions, not measured results.
- [x] Attribution/licence and historical-data limits are visible.
- [x] Generated report/JSON/chart artifacts parse and render correctly; repository links and documented commands work.
- [x] All previous-phase tests pass after documentation-generation changes.

Exit gate: complete real-data report, reproducible generation command, and `phase-5.md` evidence. A report outline without actual findings does not pass.

**Stop:** do not label the addition released before the clean-setup acceptance run.

## P6 — Verify and close the release

Entry: P5 PASS. Addresses FR-01 and FR-11.

- [x] P6-01 Follow README instructions in a fresh virtual environment; install declared runtime and development dependencies only.
- [x] P6-02 Run offline tests on the supported CI Python versions; ensure fixtures do not require the real download or provider credentials.
- [x] P6-03 Run dependency consistency/security checks, whitespace checks, and source compilation.
- [x] P6-04 Rebuild the real database and both case studies from documented commands; rerun all full-data reconciliations.
- [x] P6-05 Measure preparation time and warm filtered-view time on a recorded machine against PRD targets; record results and any resolved deviation.
- [x] P6-06 Verify all source/archive/database paths are ignored, manifests/reports expose only intended metadata/aggregates, and no key or customer-level export is tracked.
- [x] P6-07 Verify release diffs, artifact links, limitations, and the phase evidence index. Preserve unrelated work.
- [ ] P6-08 Mark all gates PASS only when evidence is complete. Commit/merge/publish only when authorised; deployment is outside this scope.

Final check commands include the following existing commands plus the implemented preparation/SQL/report commands documented during P1-P5:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt --progress-spinner off
.\.venv\Scripts\python.exe scripts/build_case_study.py
git diff --check
git status --short
```

Exit gate: all phase statuses PASS, required CI jobs pass, local full-data acceptance and measured timings are recorded, and no unresolved correctness/privacy/reproducibility blocker remains. Do not claim a live deployment or successful remote AI request without separate evidence.

## Evidence record template

Create records only when checks actually run. Replace fields with actual results; unchecked or missing evidence cannot pass a gate.

```markdown
# Phase N evidence
- Status: IN PROGRESS / FAIL / PASS / RECHECK REQUIRED
- Date/time and time zone:
- Executor/reviewer:
- Git revision and working-tree/diff reference:
- Python/interpreter, dependency versions, OS:
- Input source hash and policy/schema versions (where relevant):
- Requirements/tasks verified:

| Check/command | Expected outcome | Actual outcome | Evidence/artifact |
| --- | --- | --- | --- |

## Failures and resolution
- Issue, cause, fix, rerun result:

## Remaining limitations and blockers
- Blocking issue count:
- Accepted nonblocking limits and rationale:

## Gate decision
- Every required task/check completed: yes/no
- Upstream gates still valid: yes/no
- Gate result and rationale:
- Next phase unlocked: yes/no
```

A self-review is acceptable for this portfolio project if identified honestly. Do not invent an independent reviewer, external stakeholder approval, or CI result. Automated gate enforcement may be added later, but the implementation sequence must still follow this checklist.
