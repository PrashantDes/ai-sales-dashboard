# Sales Intelligence Dashboard

An end-to-end Streamlit analytics app for a sales manager who needs to understand performance, protect margin, spot unusual trading periods, and plan the next few months.

It is intentionally usable without a paid API: forecasting, anomaly detection, data validation, and a deterministic executive summary run locally. An optional Gemini or Claude key adds natural-language summaries and Q&A.

> **Status:** portfolio project. The default view uses reproducible synthetic Indian D2C data; no customer data or API key is required to explore it.

## What it demonstrates

| Capability | Implementation | Business value |
| --- | --- | --- |
| Data preparation | Validates a standard sales schema and cleans Tableau/Kaggle Superstore files with an auditable cleaning report | Makes assumptions and dropped rows visible |
| Decision dashboard | Period-over-period KPIs, trends, product/region performance, margin heatmap, and discount analysis | Helps a manager find revenue and profitability drivers |
| Forecasting | Damped-trend Holt-Winters forecast, approximate uncertainty band, and 3-month holdout MAPE | Provides a transparent short-term planning signal |
| Anomalies | Isolation Forest using revenue, orders, and discount relative to a rolling median | Surfaces material spikes and drops for investigation |
| AI assistance | Gemini or Claude receives aggregate tables only; rule-based summary works with no key | Adds analysis while avoiding raw orders, customer names, and IDs leaving the app |
| Reliability | Pytest coverage for the generator, validation, cleaning, forecasting, anomaly detection, and summary logic | Demonstrates that key analytical paths are tested |

## Preview

Run locally to view the generated demo data:

```bash
streamlit run app.py
```

Before publishing, add a real screenshot or short walkthrough video from your deployed instance. Do not use a screenshot containing private sales data or an exposed key.

## Run locally

Use Python 3.10–3.13 (3.11 or 3.12 recommended). Python 3.14 is intentionally excluded until all scientific dependencies publish compatible wheels.

```bash
git clone https://github.com/<your-username>/sales-intelligence-dashboard.git
cd sales-intelligence-dashboard
python -m venv .venv
```

Activate the environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\\Scripts\\Activate.ps1
```

Install and run:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
streamlit run app.py
```

## Data options

- **Generated sample (default):** reproducible Indian D2C/e-commerce data, including seasonality and injected unusual days.
- **Superstore CSV:** select or upload a Tableau/Kaggle-style Superstore CSV. It must include `Profit`, `Discount`, and `Quantity` for margin analysis. A visible **Data & EDA** tab documents the cleaning steps.
- **Your own CSV:** upload columns named `date, order_id, region, city, category, product, channel, customer_segment, units, discount, revenue, cost`. `profit` is calculated when missing. When supplied, `profit` must contain finite numeric values.

Do not commit a third-party dataset without confirming its licence. Files under `data/*.csv` are ignored by Git by default.

## Optional AI configuration

Copy the example secrets file and add only the provider key you plan to use:

```bash
copy .streamlit\\secrets.toml.example .streamlit\\secrets.toml  # Windows
# cp .streamlit/secrets.toml.example .streamlit/secrets.toml    # macOS / Linux
```

Or set `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` in your environment. `secrets.toml` is Git-ignored. Set `GEMINI_MODEL` or `ANTHROPIC_MODEL` only when you need to override the application default.

Deployment API keys stay on the server; the sidebar key field is blank and can be used to override the deployment key for that session. Credential checks use provider metadata endpoints without generating text. Q&A uses the selected date range and dimension filters.

The app sends only aggregate figures and grouped tables to an LLM. Treat this as a privacy safeguard, not a substitute for your organisation's data-governance review.

**Security note:** a Streamlit Community Cloud deployment is suitable for the generated demo data and sanitised/non-confidential files. It is not an authenticated internal analytics platform. Do not upload confidential, regulated, or production customer data to a public deployment.

## Deployment

1. Create a GitHub repository, set its default branch to `main`, and push this project.
2. In Streamlit Community Cloud, create an app with `app.py` as the entry point.
3. Add any optional API key in the platform's secret manager—never in Git.
4. Verify the generated sample flow and an uploaded-file flow after deployment.

GitHub Actions runs the test suite on Python 3.11 and 3.12 for pushes and pull requests.

## Limitations and responsible interpretation

- The forecast is univariate: it does not know future promotions, inventory constraints, pricing changes, or macro events.
- The prediction band is an approximation, not a formal statistical interval. Revenue forecasts are floored at zero, with bounds kept consistent with the forecast.
- Anomalies are flags for investigation, not causes.
- Superstore does not contain a true sales channel; its ship mode is displayed as the closest available proxy.
- LLM responses should be checked against the dashboard metrics before a decision is made.

## Repository layout

```text
app.py                    Streamlit interface
sales_ai/data.py          Generated data and standard-schema validation
sales_ai/cleaning.py      Superstore cleaning pipeline and audit report
sales_ai/ai.py            Forecasting, anomaly detection, summaries, provider adapters
tests/                    Automated tests and fake Superstore fixture
.github/workflows/ci.yml  GitHub Actions test workflow
```

## Before sharing with recruiters

- Replace `<your-username>` in the clone URL once the GitHub repository exists.
- Add one redacted screenshot or a 60–90 second walkthrough link.
- Pin a deployed demo URL near the top of this README.
- Add a licence only after choosing the terms you want others to have; none is included by default.
