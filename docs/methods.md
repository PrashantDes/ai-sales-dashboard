# Methods and tradeoffs

## Business decisions

The decision brief locates the largest absolute regional movement, sums negative-profit lines by product, and compares revenue-weighted margins on discounted versus full-price lines. It never treats those losses as recoverable savings or the margin difference as a causal discount effect. Equal-length prior windows use the same dimension filters; the UI suppresses changes if dataset coverage does not extend through the entire prior window. Missing order dates within that coverage cannot be distinguished from true zero-sales days. Profit change divides the absolute currency movement by the absolute prior profit, so reducing a loss is positive; changes from a zero base are unavailable.

## Forecasting

Monthly sums provide a small, interpretable planning series. Damped-trend Holt-Winters is a candidate because the demo contains growth and yearly seasonality; multiplicative seasonality requires 24 positive monthly observations. Promotions, inventory, and business interventions are not explanatory variables.

The last three usable monthly observations form one chronological validation window. At least six earlier months are required. A seasonal-naive baseline repeats the corresponding month from the last year when at least 12 training months exist; otherwise it repeats the last training month. Both candidates see only pre-validation values. The lower validation MAE wins, with ties favouring the baseline. The winner is refitted on all usable history. If fitting fails, a baseline remains available. With six to eight usable months the app shows an unvalidated last-month forecast; with fewer than six it declines to forecast.

MAE is mean absolute error in currency units. WAPE divides total absolute error by total absolute actual revenue; it is unavailable when all validation revenue is zero. MAPE is unavailable if any validation actual is zero. Metrics used to choose a model are not untouched test results. One three-month window is a limited comparison; rolling-origin evaluation and a later test window are required for stronger generalisation claims.

The trailing month is excluded if the last observed date is more than three days before its month-end. This is an export-coverage heuristic, not proof that a period is incomplete. The first observed month may also be partial; this is flagged rather than silently removed. Missing interior months are treated as zero sales. Forecasts are nonnegative. Bands scale historical residual spread with horizon; they have not been calibrated for 95% coverage and should not be used as risk limits.

## Anomaly screening

Isolation Forest uses log revenue and order-count ratios to centered rolling medians, plus mean line discount. Dense data uses daily totals, a 28-day window, and at least 60 periods; sparse data uses weekly totals, an 8-week window, and at least 30 periods. A period must be an Isolation Forest outlier and deviate by more than 40% from expected revenue to appear as a material flag. Sensitivity maps to contamination 0.005, 0.01, or 0.02.

The threshold is an explicit heuristic, not an optimised detector or a probability of fraud. A centered median includes future nearby observations, so this is retrospective analysis rather than a live monitoring system. Short histories show insufficient evidence, not a clean bill of health. No labelled real-world anomaly benchmark has been evaluated.

## Data quality and privacy

Cleaning exposes removed rows and transformations, while identity/range inconsistencies in custom files produce actionable errors. Exact Superstore duplicate rows are removed; legitimate multi-line orders remain. Full product names are retained as grouping identities. Standard-schema dates should be ISO; ambiguous day/month text cannot be inferred reliably. Returns need a separate accounting design before negative sales are supported.

Server keys never populate browser inputs. AI is off until enabled; no key validation happens automatically on first render. Online requests are explicitly initiated, scoped to selected dates, and use grouped tables. Labels and small groups may still reveal information, so aggregation is not anonymisation. This app has no user authentication or data-access controls.

## Reliability evidence

Pure-function tests exercise arithmetic and boundary cases. Streamlit AppTest verifies user-visible state transitions and uploads without a browser server. Provider tests verify request/response contracts and interrupted streams using mocks; they do not claim remote availability. An opt-in CLI smoke check exists for real credentials and a synthetic payload. Provider errors are sanitised, local summaries remain usable, and partial streamed answers are not silently concatenated with a second model's answer.
