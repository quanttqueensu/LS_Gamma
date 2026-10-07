# Hypothesis: skipping shorts when the VIX curve is inverted makes short gamma right more often

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-07-vix-term-gate` (config: `configs/experiments/2026-10-07-vix-term-gate.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM) |
| **Status** | failed |
| **Started** | 2026-10-07 |

## Hypothesis
Skipping short-gamma signals on days when VIX/VIX3M ≥ 1 (an inverted VIX curve) raises short precision by at least 5 points over the live rule, while keeping at least half of the short days.

## Why it matters for the desk
The bias-correction experiment (`RV_Forecasting/2026-10-07-garch-bias-correction`) found that the VRP band picks short days barely better than chance. IV beat realized vol on 68% of all days, and on 73% of live short days. The losing short days are the vol spikes, which a better point forecast doesn't catch.

An inverted VIX curve (1-month fear above 3-month fear) is the standard stress flag. It was the "VIX term gate" in the v0 signal plan (signal generation report, 2026-09-29). If it removes mostly losing days, it becomes a one-line gate in front of `vrp_band`, and the first piece of the router.

## Data
- SPY daily closes, ^VIX and ^VIX3M closes from yfinance, last 16 years. The `vix_vix3m` ratio is the same one the live pipeline builds (`pipeline/features.py`).
- IV is approximated as `0.83 × VIX`, since we have no historical ATM IV. The pass bar uses 0.83; 1.0 × VIX is reported as a sensitivity check only.
- **Hold-out:** from 2025-10-01 onward. Not used in this experiment.

## Method
- Same as live: every trading day, fit `FORECASTERS["garch"]` on the past 1,255 daily returns and forecast 21 trading days ahead (about 30 DTE). Signal from `SIGNALS["vrp_band"]` with the live bands in `configs/paper.toml`.
- **Gate:** a short signal becomes flat when VIX/VIX3M ≥ 1.0 that day. Long and flat signals are unchanged. The threshold is fixed at 1.0 and not tuned.
- **Realized vol:** `sqrt(252 × mean r²)` over the next 21 trading days. A short is "right" when IV > realized vol.
- Forecast dates stop 21 days before the hold-out. Results are by calendar year as well as overall.
- Also reported (not part of the pass bar): precision of the days the gate removes, and the median size of losing short days.
- Run: `PYTHONPATH=src python research/Agentic_Routing/2026-10-07-vix-term-gate/experiment.py`

## Metric and pass bar
- **Short precision:** share of short days where IV > realized vol.
- **Pass if all hold:**
  1. gated short precision ≥ live short precision + 5 points;
  2. gated short days ≥ 50% of live short days;
  3. at least 30 gated short days.

## If it passes
Add the gate to `src/lsgamma/signals/` as a wrapper around `vrp_band` (registered in `SIGNALS`, threshold in `configs/paper.toml`), with tests. Run it in shadow mode next to the live rule for 4 weeks, then switch `model` in `configs/paper.toml`.

## Changes
- 2026-10-07: run once (trial 1). The pass bar above was not changed.
