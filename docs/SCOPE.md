# Project scope

Version: 1.0 | Date: 2026-11-12

Read with the [PRD](PRD.md) and [phase task checklist](TASKS.md). This scope covers the existing Sales Intelligence Dashboard plus the planned real-data SQL investigation.

## Outcome

Deliver one recruiter-inspectable Data Analyst case study using UCI Online Retail: licensed source data, auditable preparation, a local SQLite model, readable SQL, independently checked results, an integrated Streamlit view, and evidence-backed recommendations.

## In scope

| Workstream | Deliverable |
| --- | --- |
| Existing baseline | Reverify the current dashboard, synthetic demo, tests, and local environment; preserve their behaviour |
| Provenance | Source attribution/licence, download/import instructions, checksum and version manifest |
| Data understanding | Actual-file profile and written inclusion/classification/precision policy |
| Preparation | Deterministic staged-to-analytical pipeline, row-disposition ledger, quality report, and failed-build protection |
| SQL/database | SQLite schema/views, justified keys/joins, parameterised queries, indexes, and query catalogue |
| Analysis | Monthly sales/cancellations, cancellation exposure by product/country, concentration, repeat purchasing |
| Validation | Fixture tests, join-cardinality tests, SQL/Python reconciliation, complete-month and missing-ID checks |
| Interface | Dedicated real-data SQL view, source/definition/quality disclosures, charts, SQL inspection, and aggregate downloads |
| Communication | Real-data Markdown case study, generated aggregate evidence, method notes, and updated README |
| Release checks | Offline CI, dependency check, full-data local acceptance, documented performance measurements, and phase evidence |

## Out of scope

- Invented cost, profit, margin, savings, or customer attributes for the UCI data.
- Verified return-to-original-sale matching, cancellation reasons, causal discount effects, or measured campaign ROI.
- Cohort retention modelling, churn prediction, forecasting extensions, or additional anomaly models for the new dataset.
- New LLM providers, AI-generated analysis as evidence, or sending the UCI transaction rows to providers.
- Power BI/Tableau ports, cloud warehouses, orchestration infrastructure, authentication, multi-user access controls, and production monitoring.
- Public deployment, paid services, employer/client approval claims, or statements of realised business impact.
- Committing the complete workbook/archive/database or distributing row-level customer identifiers.
- Replacing the existing synthetic case study; it remains a separately labelled demonstration.

These exclusions keep this release focused on DA evidence: SQL, data judgment, defensible metrics, and communication. New requests go into a later backlog rather than interrupting the phase sequence.

## Proposed repository additions

Paths below are planned; their presence in this document does not mean they exist or work yet.

```text
sales_ai/retail.py                  Preparation and read-only query access
scripts/prepare_online_retail.py    Download/import and deterministic database build
scripts/build_sql_case_study.py     Regenerate reconciled real-data evidence
sql/online_retail/                  Schema, quality checks, and named analysis queries
tests/test_retail_ingestion.py      Source/ingestion fixtures and failure handling
tests/test_retail_quality.py        Classification, precision, and row accounting
tests/test_retail_sql.py            SQL metrics, joins, rankings, and reconciliation
tests/test_retail_app.py            Real-data UI behaviours and regression checks
docs/sql-case-study.md              Actual findings/actions/limitations
docs/sql-query-catalogue.md         Question -> query -> definition -> output grain
docs/retail-data-contract.md        Frozen classification, metric, and precision policy
docs/retail-provenance.md           Attribution and source instructions
docs/evidence/phase-0.md ...        Actual gate evidence, created when checks run
data/raw/                          Ignored local source files
data/processed/                    Ignored local SQLite builds/manifests
```

Existing `app.py`, dependency files, `.gitignore`, CI, README, and method notes may change to support the addition. Existing unrelated user changes must be preserved. Published full-data evidence must contain aggregates and provenance only; synthetic row fixtures may be committed for tests.

## Phase boundaries

| Phase | Purpose | Entry requirement | Exit requirement |
| --- | --- | --- | --- |
| P0 | Establish the current baseline | Planning documents available | Existing app/tests/environment verified and evidence saved |
| P1 | Understand source and freeze definitions | P0 PASS | Actual-file profile, attribution, and data/metric contract checked |
| P2 | Build and validate the database | P1 PASS | Deterministic build, row accounting, and integrity checks pass |
| P3 | Implement and independently reconcile SQL | P2 PASS | All planned SQL questions execute and reconcile without unexplained differences |
| P4 | Integrate and verify the UI | P3 PASS | Real-data view, edge cases, state, and existing dashboard regression checks pass |
| P5 | Produce the real-data case study | P4 PASS | Report regenerated from accepted SQL; claims, attribution, privacy, and presentation checked |
| P6 | Verify the release from a clean setup | P5 PASS | Offline CI, full-data run, performance, and final evidence all pass |

Do not begin dependent implementation for the next phase until the preceding gate passes. Future planning and read-only review are allowed, but they do not advance the implementation status.

## Assumptions and dependencies

- Python and the existing project virtual environment are available; development tools may need installing into that environment.
- SQLite is provided by Python's standard library. Any workbook-reading dependency must be declared and verified rather than relying on a globally installed package.
- Source download requires network access once; normal analysis and offline tests must not.
- The source is historical and observational. Its actual quality, rather than repository metadata, determines treatment decisions.
- File-level access and public source attribution do not establish that an employer has approved the analysis or its recommendations.
- No actual data findings or exact cleaning counts are accepted until the source is downloaded and checks execute.

## Definition of done

All required tasks and gates in [TASKS.md](TASKS.md) pass with recorded evidence. The data contract, SQL, independent reconciliations, application labels, case study, and README agree. Known limitations are explicit; unresolved correctness, data-integrity, privacy, or reproducibility blockers prevent release.

Documentation creation is complete when these planning files are consistent and linked. Current implementation status is recorded in TASKS.md; completed phases require their linked gate evidence, and remaining phases must follow the sequence.
