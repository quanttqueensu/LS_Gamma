# Hypothesis: a longer wait after a stop beats the live 1-day cool-off

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-stop-cooloff` (config: `configs/experiments/2026-10-16-stop-cooloff.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | inconclusive |
| **Started** | 2026-10-16 |

## Hypothesis
Waiting longer after a stop (5 trading days, or until the signal resets) beats the live 1-day cool-off on both net P&L and tail risk.

## Why it matters for the desk
A stop is an exit rule plus a re-entry rule (Kaminski & Lo, 2014). Decision record 0003 set the re-entry rule to "no same-side entry until the next trading day" (`[exit] stop_cooloff_days = 1`) as a reasoned default, not a fitted value, and promised this test: none vs 1 day vs 5 days vs waiting for a signal reset. Volatility clusters after big moves and the VRP signal often stays short through a crash, so a 1-day wait may just re-enter the same losing trade and pay the spread twice. If a longer wait cuts the tail and adds P&L, the live rule should change; if not, the 1-day rule stays with evidence behind it.

## Data
- R2 replay snapshots, version v1 (config_hash `b040760187f0`), SPY options, run through `lsgamma.backtest` with the live code.
- **Development window:** 2014-06-02 to 2024-12-31 (the `[backtest]` default). No entries in the last 45 days before the hold-out.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used in this experiment.

## Method
- In the baseline (trial 1 of `baseline`, `configs/paper.toml`) no stop fired in 10 years, so every cool-off variant would be identical. Every variant here therefore uses the same **tighter stops**, fixed in advance and not chosen from any result: `short_stop_mult = 0.5`, `long_stop_frac = 0.25` (the same as the `tight` variant of `2026-10-16-stop-levels`). Everything else is `configs/paper.toml` (profit-take 0.5x credit, 7 DTE time exit, 3 flat days).
- Variants (`[variants.<label>]` in the TOML), all with the tighter stops:
  - `cool0`: `stop_cooloff_days = 0` (re-entry allowed at once; shows whether any cool-off matters)
  - `cool1`: `stop_cooloff_days = 1` (**reference**: the live rule)
  - `cool5`: `stop_cooloff_days = 5`
  - `reset`: `stop_cooloff_days = 0` and `[backtest] stop_reset = true` (research only: after a stop, no same-side entry until a signal other than that side has appeared; engine events `reset_wait`)
- Cool-off days are counted as weekdays (`np.busday_count`), as in `exits.cooling` live. Opposite-side entries are never blocked.
- **Comparison:** each variant against `cool1`. The baseline (trial 1) is shown in the charts for context only.
- Every variant runs at 1x and 2x spreads (one registry trial each, 8 trials).
- Costs: $0.65 per option contract, $0.005 per share, $1 minimum per order (IBKR Pro Fixed); one contract.
- Run: `PYTHONPATH=src venv/bin/python research/Risk_Management/2026-10-16-stop-cooloff/experiment.py` (once). Charts and tables only: `... experiment.py --report-only`.

## Metric and pass bar
Metrics: net P&L and ES 5% (mean of the worst 5% of daily net P&L), from `lsgamma.backtest.report.table`.

- First, if cool1 has fewer than 5 stop exits in the window (at 1x), the verdict is INCONCLUSIVE (too few events).
- Otherwise the hypothesis passes if cool5 or reset beats cool1, where "beats" = net P&L higher over the full window AND in each half (2014-06..2019-12 and 2020-01..2024-12), AND ES 5% (daily) less severe over the full window. If neither does, it fails and the live 1-day rule stays.
- Comparisons are against cool1, not the baseline, and must hold at **both 1x and 2x** spreads.

**Robustness halves:** 2014-06..2019-12 and 2020-01..2024-12 (split at 2020-01-01).

**In-sample warning:** the idea for this test (and the need for tighter stops) came from the baseline on the same development window, so any result here is in-sample evidence. Promotion needs one hold-out run.

Also reported (not part of the bar): number of stops, blocked re-entry days (`cooloff` + `reset_wait` events, distinct days) and same-side re-entries per variant; net P&L of trades opened within 10 trading days after a stop vs all other trades; the `report.standard` charts.

## If it passes
Run the winning rule once on the hold-out. If it holds: `cool5` would set `stop_cooloff_days = 5` in `[exit]` of `configs/paper.toml`; `reset` would move the signal-reset rule from `src/lsgamma/backtest/engine.py` into `src/lsgamma/trading/exits.py` with tests. Either runs in shadow mode next to the live rule before switching, and the change is recorded as a new decision record that updates 0003. Note that the result is conditional on the tighter stops; the live stop levels are tested separately in `2026-10-16-stop-levels`.

## Changes
- 2026-10-16: run once (8 trials). The pass bar above was not changed. Verdict INCONCLUSIVE: `cool1` had 3 stop exits at 1x (minimum 5). See `summary.md` and `2026-10-16-stop-cooloff.pdf`.
- 2026-10-16 (after all trials): shared research code changed, results unchanged. `lsgamma.backtest.run` now writes the registry atomically, and the `report.fees` chart legend got headroom. All figures and the PDF were rebuilt with `--report-only` (no new trials). Registry rows say `8d1f0fe-dirty` because uncommitted research files (figures, other experiments' scripts) were in the tree; `src/` and `configs/` matched 8d1f0fe.
