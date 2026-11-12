# Final pre-deployment review

Date: 2026-11-12 (Asia/Kolkata). Executor: Codex, self-review.

This review covers the synthetic QA additions, README gallery, editable architecture diagram and hosting instructions. Earlier phase acceptance records identify their own commits and environments; this record does not imply a deployed service.

| Check | Result |
| --- | --- |
| Full offline regression suite, Python 3.12 | PASS: 132 tests in 30.62s |
| `python -m pip check` | PASS: no broken requirements |
| `python -m compileall -q app.py sales_ai scripts tests` | PASS |
| `python -m pip_audit -r requirements.txt --progress-spinner off` | PASS: no known vulnerabilities at review time |
| `python scripts/verify_retail_sql.py` | PASS: all seven SQL queries match independent Python for all four scopes, including empty/injection-looking country input |
| Running Streamlit agent API | PASS: OpenAPI read; initial interaction ready |
| Headless Chromium screenshots | Four actual app captures at 1600 × 1200; no browser page errors |
| Visual review | KPI cards, product charts, forecast and retail view reviewed; SVG architecture rendered and reviewed |

The local app ran at `127.0.0.1:8766` for QA. Sales screenshots use the built-in synthetic sample; retail uses the accepted local SQLite database. Capture waits for retail metrics and removal of previous sales tabs before saving, avoiding a transient rerun image. Online AI stayed disabled, and server console output showed no new application warning or exception during capture. Screenshot browser tooling was installed only as a local QA helper, not added to runtime requirements.

The [Excalidraw source](../assets/architecture.excalidraw) and [SVG preview](../assets/architecture.svg) are generated from the same layout. Both document the current source-to-analysis-to-interface workflow, optional aggregate-only AI path, and verification layers. The generator uses no network or real records. The SVG is a matching programmatic preview, not an export claimed to have been made by the Excalidraw web editor.

## Deployment boundaries

- The generated sample and CSV upload are ready for a first hosted demo using `app.py`, `requirements.txt`, and Python 3.12.
- The historical workbook and SQLite database are ignored. A fresh host cannot use Real-data SQL until data provisioning is implemented; it displays an explicit missing-database message.
- The larger synthetic QA CSV is ignored too. It can be regenerated locally and uploaded to the hosted app.
- Empty dimension selections currently exclude all rows. The README explains how to restore selections; no filter behavior changed in this documentation update.
- Provider credentials, live requests, hosting resource capacity, public access controls and deployment operation were not validated here. No live deployment is claimed.
- Prior local performance evidence remains machine-specific. This review does not repeat the 224.2-second database rebuild because no preparation code or source changed.

The published GitHub Actions run for this change should be checked separately from this local review. The README links to the repository's Actions page for current results.
