# Online Retail data contract

Version 1.0 | Frozen for Phase 2 on 2026-11-12 | Source/schema/profile v1.0

## Grain, keys and identity

A row is a workbook invoice line. Stable staging key: workbook SHA-256 + worksheet + Excel row number (header is row 1). InvoiceNo plus StockCode is not unique. Preserve original values and string identifiers, including case. Preserve null CustomerID; never merge missing identifiers into one customer. Country belongs to the transaction. Country and customer are consistent within observed invoices; 43 invoices have multiple timestamps. Invoice time is the earliest valid timestamp, with a conflict flag; never expand invoice joins into multiple timestamp rows. Product descriptions vary for 650 codes: group on exact StockCode, not description. A display description is the most recent nonblank observation at or before the selected end date, with source-row tie-break. No forward-looking labels.

## Profiling evidence and treatments

The actual profile has 135,080 missing customer IDs, 1,454 missing descriptions, 5,268 exact duplicate-excess rows, 2,515 zero prices, 2 negative prices, 9,288 cancellation-prefixed negative lines, and 1,336 other negative-quantity lines. Counts overlap and must not be added as removals. Full aggregate evidence is in evidence/phase-1/profile.json.

All raw rows remain available. Exact duplicate-looking rows are retained and flagged by default because the source provides no line identity proving error. Phase 2 must report a separate deduplicated sensitivity view; never present it as confirmed correction. Missing descriptions do not invalidate an otherwise eligible line; display Unknown description. Missing customers remain in monetary totals but not identified-customer metrics.

## Mutually exclusive disposition precedence

1. Quarantine missing invoice/product/country, invalid dates, nonfinite numerics, noninteger quantity, negative prices, precision violations. Preserve reason(s).
2. Zero price or zero quantity: exclude as non-monetary records; preserve and flag. Negative quantity with zero price is also non-monetary, not eligible cancellation exposure.
3. Known non-merchandise codes (case-insensitive match only for this exclusion rule): POST, DOT, M, C2, D, S, BANK CHARGES, AMAZONFEE, CRUK, B, PADS, and codes starting gift_. Exclude from merchandise metrics and report separately. These are conservative analytical exclusions of charge/manual/voucher activity, not proof of their accounting treatment. Nonstandard codes alone do not establish invalidity; retain other codes, including multi-letter product suffixes and DCGS codes, with a review flag. Show policy sensitivity before generalising.
4. Invoice prefix C (case-insensitive), negative quantity, positive price: eligible cancellation; value is absolute quantity times price. C with nonnegative quantity is contradictory and quarantined (none observed).
5. Non-C invoice with positive quantity and positive price: eligible merchandise sale.
6. Other negative quantity with positive price: exclude as unmatched adjustment; do not label a verified return or cancellation (1,336 observed before other exclusions).

Precedence determines one disposition per row; overlapping quality flags remain separate. Raw counts must equal included + excluded + quarantined. Financial bridges apply only to finite, parseable values; unpriceable rows must have an explicit count rather than invented zero value. P2 must implement and test these rules before any KPI publication.

## Precision

Observed UnitPrice has at most three decimal places, including fractional pennies. Store integer thousandths of GBP, obtained using Decimal(str(source_value)) multiplied by 1000 with an exact-integer check. Reject/quarantine more precise inputs; do not silently round. Line units = whole quantity times scaled price. Check signed 64-bit bounds for each value and aggregate before SQLite insertion/summing; fail safely on overflow. SQL and independent Python must agree exactly in these units. Round only final displayed GBP amounts to pennies, using decimal half-even rounding; disclose it. Never round each line to pennies first.

## Metrics and scope

Gross merchandise sales = sum of eligible positive sales line units. Cancellation exposure = absolute sum of eligible cancellation units. Recorded net merchandise value = gross minus cancellations; other adjustments/charges remain separately reconciled. This is not audited net revenue or profit. Cancellation-to-sales ratio = cancellation exposure / gross sales in the same scope; undefined for zero sales, never clipped at 100%, and not a matched-sale return rate.

Sales invoices = distinct invoice IDs with eligible sales. Identified purchasing customers = distinct nonblank IDs with eligible sales. Within-window repeat-customer share = identified purchasing customers with two or more distinct eligible sales invoices in the selected window / identified purchasing customers in that window. Multiple lines on one invoice count once. Report identified coverage alongside customer results. Sequencing uses observed history through the selected end date only; it is not true lifetime history. Exclude cancellation invoices from purchase counts.

Concentration uses eligible gross sales with an explicit population denominator. Customer concentration excludes null IDs and discloses their sales coverage; tie-break by exact identifier for deterministic ordering. Published outputs expose rank/share, not customer IDs.

Dates are naive source-local timestamps; no timezone conversion is inferred. Inclusive date filters cover whole days. Treat December 2011 as incomplete and exclude it from default full-month comparisons. December 2010 through November 2011 are provisionally complete observed calendar months, not proof of uninterrupted exports. Missing interior months remain missing comparison coverage; LAG must compare adjacent calendar months rather than bridge gaps. Selection dates and historical nature must be shown.

## Unsupported inference and change control

No cost, profit, margin, discount effect, channel or customer-segment attributes are supplied or invented. Cancellation reasons, original-sale matching and causal effects are unavailable. No yearly seasonal forecasting extension is in scope. Version this policy and recheck dependent gates if it changes. Source hash changes require a fresh profile and contract review.
