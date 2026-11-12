# Retail SQL query catalogue

Phase 3 | Contract/schema 1.0 | Monetary integers are thousandths of GBP.

All queries live in `sql/online_retail/`. Execute using `sales_ai.retail_queries.run(connection, name, start, end, country=None)` with a read-only connection. Dates are ISO days; start is inclusive and end exclusive. Country is an exact optional bound parameter. Query names are whitelisted; neither paths nor values are interpolated from user input.

| Business question | Query | Output grain | Definition / SQL evidence |
| --- | --- | --- | --- |
| How do complete-month sales and cancellations change? | 10_monthly.sql | Observed complete month | CASE sums, CTEs, LAG; gross, cancellation, net units, distinct sales invoices; growth only for adjacent calendar months with positive prior gross |
| Which products have cancellation exposure? | 20_stock_code_exposure.sql | Exact StockCode | Gross and absolute cancellation units; ratio null on zero gross; never clipped; all eligible groups |
| Which countries have cancellation exposure? | 20_country_exposure.sql | Transaction country | Same definitions and scope; not a permanent customer-country assignment |
| How concentrated are product sales? | 30_stock_code_concentration.sql | Ranked exact StockCode | Gross sales; ROW_NUMBER with deterministic identifier tie-break; cumulative integer sums and complete-population denominator |
| How concentrated are identified-customer sales? | 30_customer_id_concentration.sql | Ranked identified customer | Same ranking; null customers excluded, denominator is identified gross sales only; internal identifiers must not be published |
| How much repeat purchasing occurs in the window? | 40_repeat.sql | One scope summary | Customers with at least two distinct eligible invoices / identified purchasing customers; coverage numerator and total gross units; empty denominator is null |
| What is the observed purchase sequence? | 41_purchase_sequence.sql | Identified customer + sales invoice | Eligible invoice grouping joined to unique invoice lookup; ROW_NUMBER partitions by customer; full observed history before end is sequenced before filtering output by start |

No top-N truncation occurs: all groups and the denominator are returned. A future UI showing top N must disclose omitted groups and preserve these denominators. Do not publish raw customer identifiers or individual purchase sequences; expose aggregated ranks/shares instead. Product labels are codes here; no future-looking descriptions are attached.

December2011 is treated as incomplete per the frozen contract. Monthly comparisons conservatively exclude the dataset's last observed month and any month not wholly inside the selection. Missing calendar months are not silently filled or bridged by LAG. Other outputs may describe the partial month when explicitly selected; this does not make it comparable with complete months. Country-filtered absence is not evidence of source completeness.

Gross sales, cancellation exposure and recorded net merchandise value follow the frozen preparation policy, retaining duplicate-looking rows. Cancellation exposure is not a matched-sale return rate. Repeat share is within-window observed purchasing, not lifetime retention. Counts use distinct invoices; multiple invoice lines do not create repeat purchases. All monetary values remain exact integers; any future GBP display must apply contract half-even rounding only at the presentation boundary.

## Independent verification

Run `.\.venv\Scripts\python.exe scripts/verify_retail_sql.py`. The oracle reads canonical line records, calculates groups/sets/rankings/sequences with independent Python loops, and compares every query row and monetary integer; it does not use the SQL aggregates as expected values. Canonical preparation was independently reconciled against staged raw Decimal values in Phase2.

The full-source, UK-filtered, partial-December and empty/injection-like country scopes run all seven queries. Published reconciliation evidence contains aggregate counts only. Fixture tests cover ties, missing customer IDs, duplicate/multi-line invoices, zero denominators, cancellation-only groups, ratios above100%, calendar gaps, partial windows, future purchases, invalid dates and rejected query inputs.

This catalogue does not claim causal cancellation reasons, realised savings, cost/profit metrics, stakeholder impact, or live business freshness. Business report conclusions and UI integration belong to later phases.
