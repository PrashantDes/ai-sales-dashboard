# Phase 2 evidence ? SQLite preparation

Status: PASS | Date: 2026-11-12, Asia/Kolkata | Branch: feat/retail-sql-investigation

Executor/reviewer: Codex self-review. Existing uncommitted work preserved; no commit, merge, push, deployment or Phase 3 business-query implementation occurred.

## Accepted deliverables

- `sales_ai/retail.py`: contract classification, exact integer units, deterministic atomic database build, read-only/parameterised access.
- `sql/online_retail/00_schema.sql`: staging, lines, invoice lookup, metadata, constraints/indexes, deduplicated sensitivity view.
- `scripts/prepare_online_retail.py`: hash-verified local workbook build command.
- [Database design and reproduction](../retail-database.md).
- `tests/test_retail_ingestion.py`: fixtures, classification/precision, row accounting, joins, nullable customers, repeated builds, read-only access, injection-safe filter, failed-build protection, overflow.

## Actual checks

| Check | Result |
| --- | --- |
| Upstream P1 | PASS; workbook hash verified against P1 manifest before preparation |
| Full source rows | 541,909 staged and accounted for |
| Mutually exclusive dispositions | 527,758 sales; 8,704 cancellations; 5,445 excluded; 2 quarantined; sum541,909 |
| Raw-to-line identity | Zero unmatched staging rows; source row primary/foreign keys retained |
| Integrity and foreign keys | integrity_check=ok; zero foreign-key violations |
| Invoice lookup | Unique invoice key; 43 multiple-timestamp flags; earliest timestamp used |
| Join preservation | Eligible row count and exact monetary sum unchanged by invoice lookup join |
| Duplicate policy | 5,268 duplicate-excess flags; rows retained in primary data; separate deduplicated sensitivity view/report |
| Independent raw Decimal reconciliation | 9,747,747,934 signed thousandths of GBP, exactly equal to analytical sum |
| Disposition monetary bridge | Sum of disposition signed units equals the same retained signed total |
| Missing customers | 135,080 flagged; nulls retained, no fictional customer grouping |
| Priceability | Zero unpriceable rows in this actual source; invalid fixture values remain explicitly unpriceable |
| Full-data repeat | Second complete workbook build produced identical report and analytical content hash |
| Second build timing | 165.55seconds, including workbook reading; local observation, not a general performance guarantee |
| Failed build | Injected pre-publication failure leaves previous database SHA-256 unchanged; temporary build removed |
| Overflow | Oversized integer fixture fails without publishing a database |
| Read access | Query-only read-only connection; attempted mutation fails; quoted/injection-like country parameter matches no unintended rows |
| Final regressions | 119 passed in26.35seconds, exit0, no warnings |
| Dependencies/whitespace | pip check clean; git diff --check clean |

Financial values here are preparation reconciliation evidence, not final business KPIs. Source price precision is preserved at thousandths of GBP; no per-line penny rounding was applied. Exclusions and overlapping flags follow contract v1.0; flag counts must not be summed as removals.

## Reproduction and evidence

```powershell
.\.venv\Scripts\python.exe scripts/prepare_online_retail.py
.\.venv\Scripts\python.exe -m pytest -o cache_dir=.venv/phase0-runtime/pytest-cache
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Tests used the established host execution context and ignored temporary/cache directories to avoid filesystem-sandbox permission issues; no warning suppression or test skipping was introduced.

- [First quality report](phase-2/quality-first.json), [second quality report](phase-2/quality.json), [full build transcript](phase-2/build.txt).
- [Independent staged-raw reconciliation](phase-2/raw-reconciliation.json).
- [Final test transcript](phase-2/tests.txt).
- [Repeat check, timing, source-file hashes and database/content hashes](phase-2/checks.json).

The local database is `data/processed/online-retail.sqlite`, ignored by Git. Its source identity includes the workbook hash, worksheet and Excel row number. Source hash43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d was verified. Analytical hash b21622ae307c7f49b14a9c584e57707a8bd1840b645d0a86d56add24eae1e09d matched across full builds. No source rows or customer IDs are published in evidence.

## Gate decision

All seven P2 tasks and required fixture/full-data checks pass. Unresolved preparation/reconciliation blockers:0. Country/customer consistency is inherited from the profiled, hash-locked source; timestamps are explicitly flagged at invoice grain. No product/customer lookup is fabricated merely to demonstrate joins. No as-of product labels or business recommendations have been implemented; those belong to P3.

P2 PASS. P3 READY, not started. Remote CI and production deployment are not claimed. Read-only mode protects this access path; it is not an OS-level security boundary against other code running as the same user.
