# Retail preparation database (schema/policy 1.0)

Build the local, hash-verified Phase 1 workbook with:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_online_retail.py
```

Source changes fail before building and require a fresh Phase 1 review. No network or provider credentials are used. The SQLite file is ignored at `data/processed/online-retail.sqlite`; aggregate preparation evidence is written to `docs/evidence/phase-2/quality.json`.

| Object | Grain/key | Purpose |
| --- | --- | --- |
| metadata | unique key | Source workbook hash, worksheet, schema/policy versions, price scale, analytical content hash |
| staging | source_row primary key | Original eight source fields as JSON; nulls retained; Excel row numbers start at2 |
| lines | source_row primary/foreign key to staging | Parsed values, exact scaled monetary units, one final disposition/reason, overlapping flags, duplicate-excess flag |
| invoices | invoice_id primary key | Earliest valid timestamp and multiple-timestamp flag; one row per invoice |
| deduplicated_sensitivity | view over lines | Alternative excluding duplicate-excess rows; retained duplicates remain the primary policy |

Full stable source identity is metadata.workbook_sha256 + metadata.worksheet + source_row. Raw values are retained as strings/null in staging, separate from trimmed analytical text. Customer identifiers remain nullable; no customer dimension with a fictional Unknown identity is created. Product descriptions stay at line grain, so a future as-of display label can be chosen without a many-to-many product join. The only lookup join is lines to unique invoices; build checks prove eligible counts and signed monetary sums are unchanged.

Price units are integer thousandths of GBP. Multiplication and signed aggregate checks occur in Python arbitrary-precision integers before SQLite SUM; overflowing data fails the build rather than silently coercing to REAL. Unpriceable rows have null values and an explicit count. Quality flags overlap; disposition counts do not.

Builds use a unique temporary database in the destination directory, enforce foreign keys and constraints, validate integrity and reconciliation, close the connection, and atomically replace the destination. Failure removes the temporary build and preserves the last valid destination. Repeated content hashes cover analytical rows in source order; schema, policy and source identity are separate metadata. No build timestamps participate in analytical identity.

Dashboard consumers must use `sales_ai.retail.readonly`, close connections, and parameterise values. `scoped_lines` is a preparation smoke-check helper using an exclusive end timestamp; it is not the Phase 3 business-query catalogue. Raw SQLite access outside this helper is not a security boundary against code running as the same OS user.

This phase prepares/reconciles data only. It does not publish sales recommendations or implement Phase 3 business analyses.
