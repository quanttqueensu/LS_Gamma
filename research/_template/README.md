# Hypothesis: <one falsifiable sentence>

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `YYYY-MM-DD-short-slug` (same as the folder and `configs/experiments/<name>.toml`) |
| **Topic** | e.g. RV_Forecasting |
| **Owner** | name (GitHub handle) |
| **Status** | planned / running / passed / failed / promoted |
| **Started** | YYYY-MM-DD |

## Hypothesis
One sentence that can be proven wrong. Example: "HAR forecasts of 20-day RV have lower QLIKE than GARCH out of sample."

## Why it matters for the desk
What changes in the live strategy if this is true?

## Data
- Source (yfinance, CRSP, R2 options, ...) and date range.
- **Hold-out:** from `YYYY-MM-DD` onward. Not used until the final run.

## Method
- Walk-forward settings (train window, test window, embargo).
- Models or rules compared, and the baseline (usually what runs live today).
- Costs and fills, if this is a trading test.

## Metric and pass bar
- Metric: e.g. QLIKE, Deflated Sharpe after costs.
- **Pass if:** e.g. "lower QLIKE overall AND in at least 5 of 7 folds".

## If it passes
The concrete next step, e.g. "set `forecaster = "har"` in `configs/paper.toml` after shadow mode".

## Changes
- (dated notes, if the plan had to change)
