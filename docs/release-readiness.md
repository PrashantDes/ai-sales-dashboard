# Reproduce the release candidate

Local Phase 6 checks passed on Windows with Python 3.11.18 and 3.12.10. Remote Ubuntu CI is pending; see [Phase 6 evidence](evidence/phase-6.md) and the [phase checklist](TASKS.md). The README's broader Python support range was not fully exercised in this verification.

Use a fresh environment from the repository root. For Windows Python 3.12:

```powershell
py -3.12 -m venv .venv/verify312
.\.venv/verify312\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv/verify312\Scripts\python.exe -m pip check
.\.venv/verify312\Scripts\python.exe -m pytest
.\.venv/verify312\Scripts\python.exe -m pip_audit -r requirements.txt --progress-spinner off
.\.venv/verify312\Scripts\python.exe -m compileall -q app.py sales_ai scripts tests
.\.venv/verify312\Scripts\python.exe scripts/build_case_study.py
git diff --check
```

Keep the scratch environment outside the repository or ensure it is ignored before staging. Repeat using Python 3.11 for the local matrix. These tests require neither a real workbook nor provider credentials. On macOS/Linux use the environment's `bin/python` executable.

For actual-data acceptance, obtain the workbook using [source provenance instructions](retail-provenance.md), verify the accepted hash and data contract, then run with the same fresh interpreter:

```powershell
python scripts/prepare_online_retail.py
python scripts/verify_retail_sql.py
python scripts/build_case_study.py
python scripts/build_sql_case_study.py
python -m streamlit run app.py
```

The `python` commands above assume the fresh environment is activated. Select Real-data SQL (GBP), inspect dates/country/quality and the four analysis sections. Reports contain historical aggregates; keep workbook, database, actual secrets and environments out of Git. Development dependencies include plotting tools required by report generation.

The existing GitHub workflow tests Python 3.11 and 3.12 on Ubuntu. It currently triggers for pushes to `main` and pull requests. Publishing only a feature branch without a pull request will not trigger it. The repository must have Actions enabled. Record actual run URLs and job results before marking P6 PASS; an empty repository needs an initial branch before a pull request can be opened.
