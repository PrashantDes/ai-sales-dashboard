# Product requirements: Sales Intelligence Dashboard and real-data SQL investigation

Version: 1.0 | Date: 2026-11-12 | Status: planned addition; [Phase 0 baseline verified](evidence/phase-0.md), [Phase 1 source contract verified](evidence/phase-1.md), [Phase 2 database verified](evidence/phase-2.md), [Phase 3 SQL verified](evidence/phase-3.md), [Phase 4 UI verified](evidence/phase-4.md), [Phase 5 report verified](evidence/phase-5.md), [Phase 6 release verification passed](evidence/phase-6.md)

Related documents: [Scope](SCOPE.md), [phased tasks and gates](TASKS.md), [existing method notes](methods.md).

## 1. Product purpose

Help a sales manager identify where to investigate sales changes, cancellation exposure, and repeat purchasing. Give a Data Analyst hiring reviewer inspectable evidence of SQL, data-quality judgment, metric definitions, reconciliation, and business communication.

The existing Python/Streamlit dashboard remains usable. The addition is one complete historical retail investigation with reproducible SQL and a concise business report. It must not invent costs, profit, realised savings, or stakeholder outcomes.

## 2. Current baseline and proposed addition

| Area | Existing implementation | Addition required |
| --- | --- | --- |
| Data | Synthetic D2C generator; custom and Superstore uploads | Licensed UCI Online Retail ingestion with provenance and a local SQLite database |
| Analytics | Decision briefs, forecast/baseline validation, retrospective anomaly screening | Inspectable SQL analysis of sales, cancellations, concentration, and repeat purchases |
| Interface | Streamlit tabs; offline default; optional online AI | Dedicated real-data SQL view with source, scope, definitions, queries, charts, and quality results |
| Evidence | Synthetic case study and regression tests | Real-data case study with independently reconciled results and limitations |

Existing code is a starting point, not evidence that Phase 0 has passed in the current environment. The previously reported test count must be rerun and recorded rather than copied into a new acceptance record.

## 3. Users and jobs

| User | Job | Successful experience |
| --- | --- | --- |
| Sales manager | Decide what to investigate before changing stock, promotions, or customer activity | Understands a finding, its supporting figures, suggested investigation, and limitations |
| DA hiring reviewer | Assess SQL and analytical reasoning | Can trace a report number through a named query to documented input treatments |
| Project maintainer | Reproduce and check the work | Can build locally, rerun tests, and regenerate outputs without keys or manual spreadsheet edits |

## 4. Business questions

1. How do recorded gross sales and cancellation values vary over complete observed months?
2. Which products and countries account for the greatest absolute cancellation exposure?
3. How concentrated are sales among products and identified customers?
4. What share of identified purchasing customers buy on more than one distinct invoice in the selected window?

Answers describe historical records. Cancellation records are not evidence of the reason for cancellation or a verified link to an earlier purchase. Customer analysis describes observed identifiers, not a complete customer population.

## 5. Data source and provenance

Use [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), credited to Daqing Chen (2015), DOI [10.24432/C5BW33](https://doi.org/10.24432/C5BW33), under CC BY 4.0. The documented source covers a UK retailer during 2010-2011 and provides invoice identifiers, product identifiers/descriptions, quantities, timestamps, unit prices in sterling, customer identifiers, and countries. The source documents invoice identifiers beginning with `C` as cancellations.

Profile the downloaded file itself. Do not infer missingness, duplicate counts, financial totals, or cleaning outcomes from metadata or previously published notebooks.

The ingestion manifest must record source URL, attribution/licence, retrieval timestamp in UTC, archive/workbook SHA-256, selected worksheet, observed rows and date bounds, schema version, preparation-policy version, and software versions. Historical dates must remain visible in the UI and report.

## 6. Functional requirements

| ID | Requirement | Acceptance evidence | Gate |
| --- | --- | --- | --- |
| FR-01 | Preserve the existing local dashboard and its public analytical functions | Current regression suite passes; local demo opens without provider requests | P0, P4, P6 |
| FR-02 | Download or import the source through a documented, repeatable command | Manifest, attribution, validated file, and a successful repeat run | P1-P2 |
| FR-03 | Preserve source-row identity and raw values; make every analytical inclusion, exclusion, or reclassification traceable | Quality report and mutually exclusive row-disposition reconciliation | P2 |
| FR-04 | Build SQLite tables/views with explicit grain, keys, constraints, and indexes | Schema tests, integrity checks, join-cardinality checks, and documented diagram/table list | P2 |
| FR-05 | Store analysis in readable, named SQL files | Query catalogue maps each business question to SQL, inputs, output grain, and metric definition | P3 |
| FR-06 | Demonstrate appropriate joins, CTEs, CASE classification, LAG, ranking, and purchase sequencing | Executable SQL and meaningful fixture assertions, not syntax-only demonstrations | P3 |
| FR-07 | Reconcile financial totals and order/customer counts independently | SQL vs Python report with no unexplained differences | P3 |
| FR-08 | Add a distinct real-data view without forcing the dataset into a fabricated cost/profit schema | UI tests confirm real-data metrics, GBP labels, source dates, and absence of invented profit | P4 |
| FR-09 | Expose definitions, quality findings, relevant SQL, and aggregate downloads | AppTest checks and manual presentation review | P4 |
| FR-10 | Publish findings and actions supported by actual computed output | Reproducible real-data report with three evidence/action/limitation findings | P5 |
| FR-11 | Provide a repeatable release verification path | Offline CI plus a documented full-data local check and evidence record | P6 |

## 7. Metric contract

These are proposed definitions to verify and freeze in P1 after profiling. Any change must update SQL, Python reconciliation, tests, UI labels, reports, and the evidence record together.

| Metric | Definition and denominator | Important limit |
| --- | --- | --- |
| Line value | Quantity multiplied by unit price, in GBP | Source precision must be preserved; do not assume every price has exactly two decimals |
| Gross merchandise sales | Sum of positive line values for eligible positive-quantity, positive-price, non-cancellation merchandise lines | Separately identify non-merchandise charges/adjustments; not audited revenue or profit |
| Cancellation value | Absolute value of eligible negative line values on cancellation-prefixed invoices | Other negative quantities or contradictory records are separately classified, not automatically called cancellations |
| Recorded net merchandise value | Gross merchandise sales minus eligible cancellation value under the same scope and policy | Excludes separately reported adjustments; not a complete accounting ledger |
| Cancellation-to-sales value ratio | Cancellation value divided by gross merchandise sales in the same selected window | Undefined when sales are zero; can exceed 100%; not a matched-sale return rate |
| Sales invoices | Distinct eligible positive-sales invoice identifiers | Lines are not orders; invoice header conflicts need an explicit treatment |
| Identified purchasing customers | Distinct nonblank customer IDs with eligible sales in scope | Missing IDs remain visible as excluded customer-analysis coverage, not fictional customers |
| Repeat-customer share in window | Identified purchasing customers with at least two distinct eligible sales invoices in the selected window divided by identified purchasing customers in that window | Undefined for an empty denominator; not lifetime retention or repeat share for unidentified customers |
| Product/customer concentration | Cumulative eligible gross sales share after descending sales ranking | Specify eligible population, missing-ID coverage, tie policy, and top-N definition |
| Monthly change | Current complete-month metric vs immediately preceding complete calendar month | Never compare a partial month with a full one; undefined for a zero prior base or missing comparison month |

Use an explicit numeric precision strategy. If scaled integers are used in SQLite, choose and document the scale after profiling, check precision loss and overflow, and reconcile exact stored units. Round monetary displays to pennies only at the presentation boundary. SQL and independent Python must use the same documented inclusion policy but separate calculation implementations.

P1 must also resolve invoice-level country/customer/timestamp conflicts, duplicate-looking lines, missing descriptions, missing IDs, nonpositive prices, non-merchandise codes, and the definition of complete observed months. No treatment may silently discard ambiguous records.

## 8. Data and database design requirements

- Preserve a staging layer with file/worksheet/source-row identifiers and original values.
- Maintain an analytical line layer with a documented disposition and reason for every staged row.
- Keep transactional country attributes at the transaction grain; do not assume a customer has one permanent country.
- Create product/customer/invoice lookup tables or views only where key uniqueness and join relationships are demonstrated. Do not add dimensions solely to display joins.
- Null customer IDs may contribute to valid monetary totals but must not be collapsed into one customer for repeat-purchase metrics.
- Keep exact repeated records available for review. Freeze an explicit duplicate policy and show its effect; do not infer accidental duplication from repeated product lines alone.
- Rerunning preparation must replace/update the intended build deterministically rather than append a second copy. A failed build must preserve the last valid database or leave a clearly unusable temporary build.
- Database access for the dashboard is read-only. Queries and filter values must use appropriate parameterisation.

## 9. User experience requirements

The real-data view shows the source, historical date coverage, GBP currency, active filters, metric definitions, and data-quality coverage before interpretation. Include at most four focused chart groups corresponding to the business questions, with detailed tables/SQL available on demand.

Missing data files, failed integrity checks, empty filters, absent customer IDs, zero denominators, and insufficient comparison coverage must produce actionable states rather than crashes or substituted synthetic figures. The existing synthetic demo must remain available without downloading the real dataset. Customer identifiers must not appear in published reports or aggregate downloads.

Online AI is not needed for the SQL investigation. The new data path must not contact AI providers or send raw transactions to them. AI-generated recommendations are not acceptance evidence.

## 10. Quality and nonfunctional requirements

- Financial reconciliations in canonical stored units must match exactly. Displayed totals may differ only by the documented final rounding rule, at most GBP 0.01 per compared displayed total; no blanket percentage tolerance.
- `raw rows = included rows + excluded rows + quarantined rows` for mutually exclusive final dispositions. Separate overlapping quality flags are reported as flags, not summed as row removals.
- Reconcile monetary values for rows with parseable, finite amounts across those dispositions. Report unpriceable rows separately; never assign a zero amount to an invalid value merely to make the bridge balance.
- Joined monetary totals and distinct invoice/customer counts must reconcile to their base grain; key duplicates must fail a check rather than inflate results.
- Missing months must not be bridged by `LAG` and presented as adjacent-month growth. Rankings and cohorts must not use observations after the selected end date.
- Normal automated tests run offline on small, purpose-built fixtures. Full-data acceptance runs separately on the downloaded source and must be recorded before release.
- Target for initial performance acceptance: on a documented development machine, full preparation within 5 minutes and a warm filtered SQL view within 3 seconds. Record hardware, data size, measured timing, and cache state. If missed, optimise or explicitly revise the target with rationale before passing the gate.
- The database/raw workbook/archive and any user secrets stay untracked. Publish only intended aggregates and small synthetic test fixtures.
- No public deployment, account setup, telemetry, or live provider billing is required to complete this addition.

## 11. Success and release acceptance

Success is a reproducible investigation, not a claimed commercial uplift. A reviewer must be able to trace every headline figure to a named SQL output, inspect the data treatment, reproduce its reconciliation, and understand an appropriate next action and limit.

Release requires all P0-P6 gates in [TASKS.md](TASKS.md) to be `PASS`, zero unresolved correctness/reconciliation/privacy blockers, complete source attribution, passing offline CI, a successful full-data local run, and an up-to-date README/report. Live deployment and proof of real-world stakeholder impact are outside this release.

## 12. Change control

The phase gates are a documented workflow, not an already implemented automated approval system. No phase is passed by creating these documents. Implementation may proceed autonomously within the agreed scope once its preceding gate has evidence; routine work does not require repeated user permission.

If a schema, source file, metric definition, or inclusion policy changes, mark affected gates `RECHECK REQUIRED`, update the traceability, and rerun their tests and downstream reconciliations before advancing. Failing checks remain failures; do not weaken tolerances or delete inconvenient records merely to pass a gate.
