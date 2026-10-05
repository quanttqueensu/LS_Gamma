# Hypothesis: HAR forecasts SPY's 20-day realized volatility better than GARCH

> Worked example of a hypothesis card. Copy `research/_template/` to start your own.

| | |
|---|---|
| **Experiment** | `2026-10-05-har-vs-garch` (config: `configs/experiments/2026-10-05-har-vs-garch.toml`) |
| **Topic** | RV_Forecasting |
| **Owner** | TBD |
| **Status** | failed |
| **Started** | 2026-10-02 |

## Hypothesis
HAR forecasts of SPY's average daily variance over the next 20 trading days have lower out-of-sample QLIKE than GARCH(1,1).

## Why it matters for the desk
The live signal uses GARCH (`forecaster = "garch"` in `configs/paper.toml`). If HAR forecasts better, switching is a one-line change and should make the VRP signal more accurate.

## Data
- SPY daily closes from yfinance, last 10 years. Daily log returns.
- **Hold-out:** from 2025-10-01 onward. Not used in this experiment.

## Method
- Expanding walk-forward: the first forecast comes after 3 years of data. Every 5th trading day both models are refit on **all returns up to that day only**, then forecast 20 days ahead.
- Forecast dates stop 20 days before the hold-out, so no target window crosses into it.
- Folds are calendar years (2019–2025). Both models come from `lsgamma.forecasting.FORECASTERS`, the same code the live runner uses.
- Run: `PYTHONPATH=src python research/RV_Forecasting/2026-10-05-har-vs-garch/experiment.py`

## Metric and pass bar
- Metric: QLIKE of forecast vs realized mean daily variance (lower is better).
- **Pass if:** HAR has lower QLIKE overall **and** in at least 5 of the 7 yearly folds.

## If it passes
Run HAR in shadow mode next to GARCH for 4 weeks, then switch `forecaster = "har"`.

## Changes
- 2026-10-02: the script was run once during setup to check it works end to end (trial 1 in the run log). The pass bar above was not changed.
