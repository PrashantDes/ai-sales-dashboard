# Phase 1 evidence

Status: PASS | Date: 2026-11-12, Asia/Kolkata | Branch: feat/retail-sql-investigation

Executor/reviewer: Codex self-review. No independent human or remote CI approval is claimed. Existing uncommitted work was preserved; no commit or push occurred.

## Deliverables

- [Provenance and reproduction](../retail-provenance.md)
- [Frozen data contract v1.0](../retail-data-contract.md)
- [Source manifest](phase-1/manifest.json), [actual-file profile](phase-1/profile.json), [repeat profile](phase-1/profile-first.json)
- [Gate checks](phase-1/checks.json), [test transcript](phase-1/tests.txt)
- Acquisition/profile script: `scripts/profile_online_retail.py`; invented edge fixtures: `tests/retail_fixture.py`.

## Checks performed

| Check | Result |
| --- | --- |
| P0 prerequisite | PASS; baseline evidence retained |
| Official source/licence/attribution | UCI Online Retail, DOI10.24432/C5BW33, CC BY4.0; source page checked |
| Declared workbook reader | openpyxl3.1.5 installed in isolated Python3.12.10 environment |
| Acquisition | Official archive downloaded with timeout/size checks; expected workbook selected explicitly without arbitrary path extraction |
| Required schema and actual worksheet | All eight expected columns; Online Retail worksheet |
| Provenance | SHA-256 for archive/workbook, observed rows, UTC record/retrieval times, versions; retrieval time is explicitly based on downloaded archive mtime |
| Profile repeatability | Two offline profiles of the same workbook match exactly |
| Profile findings | 541,909 rows; 135,080 missing customer IDs; 1,454 missing descriptions; 5,268 duplicate-excess rows; 43 invoice timestamp conflicts; fractional-penny prices have up to3 decimals |
| Precision/denominators | Contract specifies exact thousandths of GBP, overflow checks, unknown-customer coverage and undefined zero denominators |
| Duplicate/cancellation treatment | Repeated lines retained/flagged; cancellation-prefix negative lines separated from unmatched adjustments; no verified return linkage asserted |
| Synthetic fixtures | Ordinary, repeated, missing-ID/description, contradictory sign, negative/zero price, invalid date/numeric, nonmerchandise and excess-precision records |
| Raw/database ignore checks | Raw archive/workbook and processed SQLite paths ignored; zero tracked raw files |
| Environment consistency | pip check: no broken requirements |
| Regression suite | 116 passed in12.85s, exit0, no warnings |
| Whitespace | git diff --check passed |

Commands: `.venv/Scripts/python.exe scripts/profile_online_retail.py --download`, followed by the same command without `--download`; `.venv/Scripts/python.exe -m pip check`; `.venv/Scripts/python.exe -m pytest -o cache_dir=.venv/phase0-runtime/pytest-cache`; `git diff --check`.

Tests used the documented Phase0 host execution context and ignored temporary/cache directories to avoid sandbox cleanup permission errors. No test skip or warning suppression was added. The HTTP browsing tool could not fetch the archive because of its size; the bounded Python download succeeded. No application or analytical database was built.

## Limits and gate decision

Data quality flags overlap; counts are not additive removals. Nonstandard product code syntax alone does not establish invalid merchandise. The conservative nonmerchandise policy and duplicate sensitivity must be implemented, reconciled and tested in Phase2 before KPI publication. No actual business recommendation or SQL financial result is accepted here. Downloaded historical data contains no cost field, so profit/margin must not be fabricated.

All seven Phase1 deliverables and required checks are complete. Blocking issues:0. P1 PASS; P2 READY, not started. No real source rows/customer identifiers were published. These documents do not authorise deployment or claim stakeholder impact.
