# Phase 6 release verification

- Status: BLOCKED — local checks PASS; GitHub Actions pending.
- Verification date: 2026-11-12, Asia/Kolkata. Executor: Codex; self-review, no independent reviewer claimed.
- Candidate: `feat/retail-sql-investigation`, base `7789d0632068378bbdef0d5485435c3042ce8ad5`, including existing uncommitted work. [Source hashes](phase-6/source-snapshot.json) identify the tested source; subsequent edits document these results.
- Upstream P0–P5 remain accepted. No product code changed for P6.

## Local acceptance results

| Check | Actual result | Evidence |
| --- | --- | --- |
| Fresh declared development/runtime installation | PASS on Windows Python 3.11.18 and 3.12.10 | [3.11 environment](phase-6/py311-environment.json), [3.12 environment](phase-6/py312-environment.json) |
| Offline regression suite in isolated source copy | 129 passed on each interpreter; 28.75s / 34.54s; no source workbook, database or provider keys | [3.11 output](phase-6/py311-tests.txt), [3.12 output](phase-6/py312-tests.txt) |
| Dependency consistency, compilation, synthetic regeneration | All commands exit 0 on both interpreters | Environment records above contain commands and timings |
| Runtime dependency audit | No known vulnerabilities; zero skipped dependencies on both interpreters | [3.11 audit](phase-6/dependency-audit-py311.json), [3.12 audit](phase-6/dependency-audit.json) |
| Actual workbook preparation | PASS; 224.2s against 300s target | [Build output](phase-6/database-build.txt), [pipeline and hardware](phase-6/pipeline.json) |
| Independent full-data SQL reconciliation | PASS; 11.5s | [Reconciliation output](phase-6/sql-reconciliation.txt) |
| Both case studies regenerated | PASS; synthetic 3.31s, real 12.27s; database and all seven report artifact hashes unchanged | [Pipeline hashes](phase-6/pipeline.json) |
| Warm filtered real-data view | PASS; 0.172s, 0.188s, 0.171s against 3s target; headline matches accepted SQL | [Performance record](phase-6/view-performance.json) |
| Privacy and ignore rules | No detected credential patterns or raw/database candidate files; real report excludes customer-level rows | [Scan scope and results](phase-6/privacy-and-audit.json) |

Fresh environments installed only `requirements-dev.txt`, which includes runtime requirements. Exact resolved distributions are recorded in [3.11](phase-6/py311-verified-dependencies.txt) and [3.12](phase-6/py312-verified-dependencies.txt) QA snapshots; these are not production lockfiles. Python 3.11 was obtained through uv's managed interpreter installation inside ignored `.venv/phase6`; no system PATH/registry change was made. Scientific dependencies differ slightly between interpreters.

## Reproduction

Follow [release readiness instructions](../release-readiness.md). Each fresh interpreter ran `python -m pip check`, `python -m pytest`, `python -m compileall -q app.py sales_ai scripts tests`, and `python scripts/build_case_study.py` against an isolated source copy. Provider key environment variables were removed and no actual secrets file was copied. Both interpreters ran `python -m pip_audit -r requirements.txt --progress-spinner off -f json`.

The full-data run used fresh Python 3.12 and the accepted workbook already present locally: `scripts/prepare_online_retail.py`, `scripts/verify_retail_sql.py`, `scripts/build_case_study.py`, and `scripts/build_sql_case_study.py`. The workbook and database remain ignored.

Hardware: Windows 11 build 26300, Intel64 Family 6 Model 151 Stepping 2, 12 logical CPUs. Performance measured a running Streamlit 1.67.0 app using localhost agent API requests, including server view generation and JSON transfer, excluding browser JavaScript and paint. Initial demo took 3.453s; first real view 3.907s; first filtered scope 1.312s. The 3s requirement is explicitly for warm filtered requests. Scope was United Kingdom, 2011-03-01 through 2011-09-30 inclusive. Server console showed no application exception during these requests. P4's user-confirmed visual review remains separate evidence.

## Gate decision and remaining blocker

The [task checklist](../TASKS.md) requires successful CI jobs. Local Windows runs do not establish Ubuntu GitHub Actions success. The supplied repository `https://github.com/PrashantDes/ai-sales-dashboard` was reachable with no advertised refs and configured as `origin`. No push, remote CI run, merge, deployment or online AI request is claimed.

P6 remains BLOCKED until the reviewed candidate is published with authorization and both required Python jobs pass. No earlier phase is reopened by these documentation-only changes. Dependency audits are point-in-time checks, and pattern scanning cannot guarantee detection of every secret format.
