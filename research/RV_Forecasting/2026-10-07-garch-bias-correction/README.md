# Hypothesis: removing GARCH's trailing bias makes the VRP band pick better days

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-07-garch-bias-correction` (config: `configs/experiments/2026-10-07-garch-bias-correction.toml`) |
| **Topic** | RV_Forecasting |
| **Owner** | Gabe Soler (PM) |
| **Status** | failed |
| **Started** | 2026-10-07 |

## Hypothesis
Scaling the live GARCH forecast by its own median error over the past year removes its upward bias, and with the live VRP bands this makes short-gamma days right more often than they are now (at least 5 points more), and long-gamma days right more often than not.

## Why it matters for the desk
A quick replay (2026-10-06) found the live GARCH forecast runs about 3 vol points above the vol SPY then realizes. The 5-year fit window includes 2022, so the forecast leans toward a long-run level of about 16.5%. As a result:
- long signals fired on days when IV still ended above realized vol 67% of the time;
- short signals were right 73% of the time, barely better than flat days (70%).

If a simple correction fixes this, the signal improves without touching the bands. Bands should only be tuned once the forecast is unbiased.

## Data
- SPY daily closes and ^VIX closes from yfinance, last 16 years (needed for a 5-year rolling window plus a 1-year bias window before the first test date).
- **No historical ATM IV is available**, so IV is approximated as `0.83 × VIX` (the ratio seen in the 2026 live snapshots). The pass bar uses 0.83; results at 1.0 × VIX are reported as a sensitivity check only.
- **Hold-out:** from 2025-10-01 onward. Not used in this experiment.

## Method
- Same as live: every trading day, fit `FORECASTERS["garch"]` on the past 1,255 daily returns and forecast 21 trading days ahead (about 30 DTE).
- **Realized vol:** `sqrt(252 × mean r²)` over the next 21 trading days.
- **Corrected forecast:** `forecast × exp(−b)`, where `b` is the median of `log(forecast / realized)` over the past 252 forecasts whose 21-day target window had already **finished** by that day. This means no look-ahead.
- **Signals:** both forecasts go through the live `SIGNALS["vrp_band"]` with the live bands from `configs/paper.toml` (short above +2, long below −5).
- Forecast dates stop 21 days before the hold-out. Results are by calendar year as well as overall.
- Run: `PYTHONPATH=src python research/RV_Forecasting/2026-10-07-garch-bias-correction/experiment.py`

## Metric and pass bar
- **Bias:** median of (forecast vol − realized vol).
- **Short precision:** share of short days where IV > realized vol (the option seller wins on vol).
- **Long precision:** share of long days where realized vol > IV (the option buyer wins on vol).
- QLIKE is reported as a diagnostic only.
- **Pass if all three hold:**
  1. |median bias| of the corrected forecast < 1 vol point;
  2. corrected short precision ≥ baseline short precision + 5 points;
  3. corrected long precision > 50%.

  Each side needs at least 30 signal days, otherwise that test fails.

## If it passes
Add a bias-corrected wrapper to `src/lsgamma/forecasting/` (registered in `FORECASTERS`), with tests. Run it in shadow mode next to live GARCH for 4 weeks, then switch `forecaster` in `configs/paper.toml`. After that, consider tuning the bands.

## Changes
- 2026-10-07: run once (trial 1). The pass bar above was not changed.
