# Phase 0 evidence — baseline verified

- **Gate: PASS**
- Date: 2026-11-12, Asia/Kolkata (UTC+05:30). Exact check timestamps are in the linked JSON records.
- Executor: Codex, with delegated artifact verification and self-review. No independent human approval or remote CI run is claimed.
- Branch: `feat/retail-sql-investigation`.
- Base commit: `7789d0632068378bbdef0d5485435c3042ce8ad5`.
- Working state: existing modified and untracked project files were preserved. A branch was created from the existing `main`; nothing was staged, committed, merged, or pushed during P0.
- Scope: existing dashboard/environment only. No UCI source was downloaded and no Phase 1 implementation was started.

## Verified environment and revision

The isolated project interpreter is `.venv/Scripts/python.exe`, Python 3.12.10 on Windows 11. System site packages are disabled. Development dependencies were installed from `requirements-dev.txt` into that environment.

| Component | Verified version |
| --- | --- |
| Streamlit | 1.67.0 |
| pandas | 2.3.3 |
| NumPy | 2.4.6 |
| Plotly | 6.9.0 |
| scikit-learn | 1.9.1 |
| statsmodels | 0.15.0 |
| anthropic | 0.125.0 |
| google-genai | 3.1.0 |
| groq | 1.7.0 |
| pytest | 9.2.0 |
| pip-audit | 2.10.1 |

[Environment and SHA-256 file manifest](phase-0/environment.json) identifies the verified app, analytical modules, scripts, tests, dependency declarations, and configuration. The final check confirmed those hashes still matched. This is a baseline of the current dirty working tree, not just the older base commit.

## Required checks

| Task | Actual result | Evidence |
| --- | --- | --- |
| P0-01 Branch and preservation | Created `feat/retail-sql-investigation`; existing work retained; staging area empty; virtual environment, secrets path, and local CSV probe are ignored | [Initial working state](phase-0/initial-environment.json), [final checks](phase-0/final-checks.json) |
| P0-02 Interpreter/dependencies | Isolated supported Python; runtime/dev dependencies installed; `pip check` exited 0 with “No broken requirements found” | [Environment](phase-0/environment.json), [pip check](phase-0/pip-check.txt) |
| P0-03 Regression suite | **114 passed in 12.88s, zero warnings**, exit 0 on final verification run | [Test transcript](phase-0/pytest.txt), [commands/results](phase-0/checks.json) |
| P0-04 Synthetic artifacts | Regenerated case study; JSON and SVG XML parse; two same-environment builds have identical SHA-256 hashes and match the repository artifacts | [Artifact checks](phase-0/artifacts.json) |
| P0-05 Existing demo | All tabs and edge states passed AppTest; running app independently exercised through its localhost agent API | [Live app checks](phase-0/live-app.json), [test transcript](phase-0/pytest.txt) |
| P0-06 Warnings/disposition | NumPy compatibility issue resolved; sandbox permission failures isolated from application behaviour; final host run clean | Logs and disposition below |

Commands used:

```powershell
git switch -c feat/retail-sql-investigation
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/build_case_study.py
git diff --check
```

After the compatibility adjustment, the final regression command was:

```powershell
.\.venv\Scripts\python.exe -m pytest -o cache_dir=.venv/phase0-runtime/pytest-cache
```

For final verification, `TEMP`/`TMP` pointed to `.venv/phase0-runtime/temp`, and the test process ran outside the restricted filesystem sandbox. All existing tests were collected; no warning filters, test skips, or disabled pytest plugins were introduced to manufacture a clean result. The cache override affects only test artifacts.

## Running app verification

A temporary Streamlit instance was bound to localhost, with usage statistics disabled:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --server.port=8765 --server.enableAgentApi=true --browser.gatherUsageStats=false
```

The server's generated OpenAPI schema was read before interacting. Health returned `ok`; every checked run returned `ready`. Checks covered:

- Overview: five KPI cards, online AI off, inactive forecast not evaluated.
- Products & Regions, Forecast, Anomalies, AI Insights, and Data & EDA: no application exception.
- Forecast: validation WAPE displayed as 4.1%; horizon remained 12 after leaving and returning to the tab.
- AI Insights: deterministic headline available, online mode off, question input disabled without online access.
- Empty region selection: clear warning and no stale KPI cards.
- Upload mode without a file: an upload prompt rather than substituted synthetic results.
- Returning to generated data: successful run.

Server console output showed no warnings or traceback during these requests. The temporary server was stopped and its health endpoint was confirmed unavailable afterwards. The agent API does not execute browser layout or file-upload actions: actual custom/Superstore uploads and cleaning reports were verified by the existing AppTest cases, including invalid-upload rejection. No live provider request or real credential was used. No browser/DOM or visual-layout acceptance is claimed for P0.

## Artifact and analytical checks

The artifact verification independently recomputed selected-period totals and the decision brief from the generator, checked grouped reconciliation, parsed JSON/SVG, reconstructed the SVG, checked local Markdown links, and verified rounded README claims. Two builds under ignored `.venv/phase0-artifact-check/` produced identical output hashes.

- Selected revenue: INR 91,606,978.18.
- Recorded profit: INR 21,945,383.77 when rounded for display.
- Orders: 7,151.
- Recorded margin: 23.9560%.
- Holt-Winters validation WAPE: 4.1333%; seasonal-naive validation WAPE: 18.6815%.

These remain synthetic results, and the forecast scores are validation scores used for selection. They are not evidence of independent-test accuracy or real commercial impact.

Regeneration changed the Markdown/JSON hashes from the artifacts present before P0; SVG did not change. Exact pre-run bytes were not retained, so no precise old-versus-new numerical difference is asserted. Final outputs are reproducible under the recorded environment and their rounded README statements remain correct. Initial and final artifact checks are both retained.

## Failures, warnings, and resolution

### NumPy/pandas compatibility

The initial environment selected NumPy 2.5.4 with pandas 2.3.3. The initial suite passed all 114 tests but emitted 19,743 warnings, dominated by generic-timedelta deprecations. Artifact generation also emitted those deprecations. This is a forward-compatibility issue, not a failed business assertion. NumPy documents the [generic-timedelta deprecation beginning in 2.5](https://numpy.org/doc/stable/reference/arrays.datetime.html).

`requirements.txt` was narrowed to `numpy>=1.26,<2.5` for the current pandas 2.x paths; NumPy 2.4.6 was installed in `.venv`. Regeneration then emitted zero warnings, remained deterministic, and matched the first P0 regeneration's output hashes. The final regression run was also free of dependency deprecations. Revisit this bound when upgrading the pandas/NumPy combination; do not suppress these warnings globally.

The package replacement reported that ignored `~umpy` uninstall-backup directories could not be removed automatically. Active NumPy is 2.4.6, dependency consistency and imports succeed, and those backups are not staged or part of the application. This is a local environment cleanup note, not an application blocker.

### Filesystem sandbox permissions

Both the original cache location and a redirected cache/temp location produced permission warnings or shutdown cleanup tracebacks inside the restricted sandbox, despite test exit 0. After correcting the NumPy bound, the sandbox run had 114 passing tests and one cache warning; its cleanup traceback was separate from test execution. The same environment/tests outside that sandbox passed without the cache warning or cleanup traceback.

Records are retained rather than hidden:

- [Initial environment](phase-0/initial-environment.json), [initial checks](phase-0/initial-checks.json), [initial test transcript](phase-0/initial-pytest.txt).
- [Post-adjustment sandbox checks](phase-0/sandbox-checks.json), [sandbox transcript](phase-0/sandbox-pytest.txt).
- [Initial artifact verification](phase-0/initial-artifacts.json), [final artifact verification](phase-0/artifacts.json).
- [Final test transcript](phase-0/pytest.txt), [final checks](phase-0/final-checks.json).

## Gate decision

- All six P0 tasks: complete.
- Required checks: pass.
- Unresolved application-correctness/dependency-consistency blockers: **0**.
- Nonblocking limits: local Python 3.12 verification only; no remote CI, browser-layout acceptance, live provider availability, deployment, or real-data findings are claimed. Those are not P0 prerequisites.
- Upstream gates: none.
- **P0: PASS. P1: READY, not started.**

No new dataset or downstream implementation is authorised by this evidence record itself. Continue with P1 only when requested within the project's agreed scope.
