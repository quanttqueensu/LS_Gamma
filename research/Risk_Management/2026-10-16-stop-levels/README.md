# Hypothesis: tighter stops cut the daily tail at a small cost; a 25% take-profit on shorts adds P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-stop-levels` (config: `configs/experiments/2026-10-16-stop-levels.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (H1 failed, H2 failed) |
| **Started** | 2026-10-16 |

## Hypothesis
- **H1 (primary):** tighter stops (short stop at 0.5x credit instead of 1.0x, long stop at 0.25x premium instead of 0.5x) cut the daily 5% expected shortfall of the book by at least 20% at a small cost in net P&L.
- **H2:** a take-profit on shorts at 25% of the credit (instead of 50%) raises net P&L without making the daily tail worse.

## Why it matters for the desk
The live exits (`src/lsgamma/trading/exits.py`, `[exit]` in `configs/paper.toml`) close a short when its combined P&L reaches -1.0x the credit, a long when it loses 0.5x the premium, and take profit on a short at +0.5x the credit. They are checked at every scheduled run (10:15 daily). In the baseline backtest **none of them ever fired** in 10 years: the worst short reached -0.78x credit, the best short +0.35x credit and the worst long -0.28x premium. So today the desk has no working loss limit or profit-take; every position exits on time, flip or flat signals. If H1 passes, the stops become a real limit on the worst days. If H2 passes, shorts bank their decay earlier and free the book for the next signal.

## Data
- R2 replay snapshots `v1` (`data/backtest/v1`, config_hash `b040760187f0`), built from the club's R2 option trades with the live pipeline code.
- **Development window:** 2014-06-02 to 2024-12-31 (the `[backtest]` default). No entries in the last 45 days before the hold-out.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used in this experiment.

## Method
- Variants, each a `[variants.<label>]` table in the TOML; everything else is `configs/paper.toml` + `configs/backtest.toml`:
  - `tight`: `short_stop_mult = 0.5`, `long_stop_frac = 0.25` (primary, H1)
  - `profit25`: `short_profit_frac = 0.25` (H2)
  - `both`: all three changes (reported only, no bar)
- `stop_cooloff_days` stays at the live 1 in every variant.
- **Comparison:** baseline trial 1 (experiment `baseline` in `results/research/registry.parquet`, the paper rules on the same window), at the same spread multiple.
- Each variant runs at 1x and 2x spreads through `lsgamma.backtest.run.variants` (one registry trial per variant and multiple, 6 trials).
- Costs: $0.65 per option contract, $0.005 per share, $1 minimum per order (IBKR Pro Fixed). Options and shares fill at the modelled mid plus or minus the modelled half-spread times the multiple.
- Metric: daily 5% expected shortfall (ES 5%, the mean of the worst 5% of daily net P&L, `metrics.expected_shortfall`) and net P&L, from `lsgamma.backtest.report.table`.
- Run: `PYTHONPATH=src python research/Risk_Management/2026-10-16-stop-levels/experiment.py` (once). `--report-only` rebuilds the charts and tables from the registered runs.

## Metric and pass bar
Compared with baseline trial 1 at the same spread multiple; each must hold at BOTH 1x and 2x:

- **H1 (tight):** |ES 5% (daily)| <= 0.80 x |ES 5%| of baseline over the full window, AND ES 5% is less severe than baseline in each half (2014-06..2019-12 and 2020-01..2024-12), AND net P&L >= baseline net P&L - $300 over the full window.
- **H2 (profit25):** net P&L > baseline over the full window AND in each half, AND |ES 5%| <= 1.10 x |ES 5%| of baseline.

Each hypothesis gets its own verdict; the experiment verdict lists both (e.g. "H1 passed, H2 failed"). `both` is reported only.

**Robustness halves:** 2014-06..2019-12 and 2020-01..2024-12 (`report.SPLIT = 2020-01-01`).

**In-sample warning:** the idea came from the baseline on the same window (no stop or profit-take fired there), so this is in-sample evidence. Promotion needs one hold-out run.

## If it passes
- H1: set `short_stop_mult = 0.5` and `long_stop_frac = 0.25` in `[exit]` of `configs/paper.toml`, after one hold-out run and a few weeks in shadow mode next to the live rule.
- H2: set `short_profit_frac = 0.25` the same way.
- Record the decision in `docs/decisions/`.

## Changes
- 2026-10-16: run once (6 trials: 3 variants at 1x and 2x). The pass bar above was not changed. `exits_per_year.png` was rebuilt with `--report-only` (y-axis shared per row instead of across all panels); no new trials.
- 2026-10-16 (after all trials): shared research code changed, results unchanged. `lsgamma.backtest.run` now writes the registry atomically, and the `report.fees` chart legend got headroom. All figures and the PDF were rebuilt with `--report-only` (no new trials). Registry rows say `8d1f0fe-dirty` because uncommitted research files (figures, other experiments' scripts) were in the tree; `src/` and `configs/` matched 8d1f0fe.
