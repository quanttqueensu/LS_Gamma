# Hypothesis: a 10-share hedge band beats re-hedging every share

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-hedge-band` (config: `configs/experiments/2026-10-16-hedge-band.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | passed (development window; hold-out run still to do) |
| **Started** | 2026-10-16 |

## Hypothesis
Re-hedging only when the delta drift reaches 10 shares (a hedge band) gives higher net P&L than re-hedging every share, because it cuts $1-minimum hedge orders, and it does so without a worse tail.

## Why it matters for the desk
The book trades one contract, so a hedge order is almost always 1 to 100 shares. At $0.005 a share that is under $1, so every hedge order pays the $1 IBKR minimum. In the baseline backtest (2014-06-02 to 2024-12-31), hedges cost $914 over 914 orders, more than three times the $262 of option commissions, and the book lost $2,059.5 net at 1x spreads. An order for 3 shares pays the same $1 as an order for 90. Skipping small rebalances is the simplest hedging policy that is not "hedge every share", and it is the first benchmark any later deep-hedging policy has to beat.

The live code already has this rule: `[hedge] min_shares` in `configs/paper.toml` (default 1) is passed to `portfolio.rebalance()`, and the backtest engine (`lsgamma.backtest.engine.hedge`) uses the same rule. If it passes, promotion is one line in `paper.toml`.

## Data
- R2 replay snapshots, version `v1` (`config_hash` b040760187f0), built by `lsgamma.history.build`.
- **Development window:** 2014-06-02 to 2024-12-31 (the `[backtest]` default). Every result on this card comes from it.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used in this experiment.

## Method
- **Rule:** at each hedge time (10:15 ET, once a day, as live), the engine computes the target share hedge from the position's delta. If |target - held| < `min_shares`, it does nothing. Otherwise it trades the full difference back to the target. The band also applies after a position closes (target 0), so fewer than `min_shares` shares can stay on the book while flat or carry into the next position, as they would live.
- **Variants** (`[variants.<label>.hedge] min_shares = N`, nothing else changed from `paper.toml` + `backtest.toml`):
  - `band5`: `min_shares = 5` (sensitivity only)
  - `band10`: `min_shares = 10` (**primary**, the only variant the pass bar uses)
  - `band20`: `min_shares = 20` (sensitivity only)
- **Comparison:** baseline trial 1 in `results/research/registry.parquet` (experiment `baseline`, `min_shares = 1`): 1x net P&L -$2,059.5, ES 5% -96.5; 2x net P&L -$4,122.3, ES 5% -104.5.
- **Spreads:** every variant runs at 1x and 2x spreads (`lsgamma.backtest.run.variants`). Each variant and multiple is one registry trial (6 trials).
- **Costs:** $0.65 per option contract, $0.005 per share, $1 minimum per order (IBKR Pro Fixed); hedge fills 0.5 cents from spot at 1x.
- Run: `PYTHONPATH=src venv/bin/python research/Deep_Hedging/2026-10-16-hedge-band/experiment.py` (once). `--report-only` rebuilds charts and tables from the registered runs without new trials.

## Metric and pass bar
Primary variant `band10` only, compared with baseline trial 1 at the same spread multiple; must hold at BOTH 1x and 2x:
1. Net P&L of band10 > baseline over the full window AND in each half (2014-06..2019-12 and 2020-01..2024-12);
2. |ES 5% (daily)| of band10 <= 1.10 x |ES 5%| of baseline (full window).

Both at both multiples = pass; otherwise fail. band5 and band20 are reported as sensitivity only and cannot change the verdict.

- **Robustness halves:** 2014-06..2019-12 and 2020-01..2024-12 (`lsgamma.backtest.report.table`, split at 2020-01-01). They are part of bar 1.
- ES 5% is the mean of the worst 5% of daily net P&L (`lsgamma.backtest.metrics.expected_shortfall`).

**In-sample warning:** the idea came from the baseline run on this same window (the hedge-fee total), so a pass here is in-sample evidence only. Promotion needs one hold-out run.

## If it passes
1. Run `band10` once on the hold-out (`--holdout`), with the same pass bar.
2. If that holds, run `min_shares = 10` in shadow mode next to the live hedge (`min_shares = 1`) for a few weeks on paper.
3. Then the PM decides whether to set `[hedge] min_shares = 10` in `configs/paper.toml`, recorded in `docs/decisions/`.

## Changes
- 2026-10-16: run once (6 trials). The report step crashed on a registry read while parallel experiments were writing, after all 6 trials were registered. Charts and tables were rebuilt with `--report-only` (no new trials). After the run, `experiment.py` gained report-only diagnostics (a share P&L split, a P&L bridge chart, and the hedge charts merged into one figure). The pass bar above was not changed.
- 2026-10-16 (after all trials): shared research code changed, results unchanged. `lsgamma.backtest.run` now writes the registry atomically, and the `report.fees` chart legend got headroom. All figures and the PDF were rebuilt with `--report-only` (no new trials). Registry rows say `8d1f0fe-dirty` because uncommitted research files (figures, other experiments' scripts) were in the tree; `src/` and `configs/` matched 8d1f0fe.
