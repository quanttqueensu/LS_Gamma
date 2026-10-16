# Hypothesis: turning long gamma off (short-only) gives higher net P&L than the live rule after costs, without a worse tail

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-short-only` (config: `configs/experiments/2026-10-16-short-only.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-16 |

## Hypothesis
On the R2 option backtest (2014-06-02 to 2024-12-31), a book that never goes long gamma (`long_band = -inf`) makes more net P&L after costs than the live `vrp_band` rule, at both 1x and 2x spreads and in both halves of the window, without a materially worse daily tail or drawdown.

## Why it matters for the desk
In the baseline backtest (trial 1, live `configs/paper.toml`), the 30 long trades lost $1,913 net at 1x, while the 101 short trades lost only $148 net (+$721 gross). Long gamma is most of the loss. If the long side has no edge after costs, the simplest router is "short or flat": the long band would be switched off and the desk would stop paying for long premium and its hedges. It is also the first question any router must answer: is long gamma worth having on the menu at all?

## Data
- R2 replay snapshots `v1` (`config_hash` b040760187f0), option trades from the club R2 bucket replayed with the live code.
- **Development window:** 2014-06-02 to 2024-12-31 (the `[backtest]` default).
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used in this experiment.

## Method
- One variant, `short_only`: `[variants.short_only.signal] long_band = -inf`. VRP can never be below it, so the long signal never fires. Everything else is `configs/paper.toml` + `configs/backtest.toml`. No code change.
- Comparison: baseline trial 1 (experiment `baseline` in the registry) at the same spread multiple.
- Run with `lsgamma.backtest.run.variants` at 1x and 2x spreads (2 trials).
- Costs: $0.65 per option contract, $0.005 per share, $1 minimum per order; fills at the modelled half-spread times the multiple.
- **This compares whole books, not the short trades alone.** With `max_positions = 1`, removing long trades frees the single position slot, so short_only can open shorts on days when the baseline was holding a long. Short exits also change: a long signal no longer closes a short by "flip"; that day counts as flat instead, so a short closes by the flat rule (3 flat days), time, stop or profit. So the short trades of short_only are not a subset of the baseline's shorts.
- Run: `PYTHONPATH=src python research/Agentic_Routing/2026-10-16-short-only/experiment.py` (`--report-only` rebuilds charts and tables from the registered runs without new trials).
- Charts (`figures/`): the standard set (cumulative P&L, drawdown, yearly, by exit reason, fees) and net P&L by side (long vs short) for baseline vs short_only at 1x and 2x.

## Metric and pass bar
Compared with baseline trial 1 at the same spread multiple; must hold at BOTH 1x and 2x:
1. Net P&L of short_only > baseline over the full window AND in each half (2014-06..2019-12 and 2020-01..2024-12);
2. |ES 5% (daily)| of short_only <= 1.10 x |ES 5%| of baseline (full window);
3. max drawdown of short_only <= 1.10 x baseline max drawdown (full window).

All three at both multiples = pass; otherwise fail.

Robustness halves: 2014-06..2019-12 and 2020-01..2024-12 (part of bar 1).

**In-sample warning:** the idea came from the baseline result on this same window, so a pass here is in-sample evidence only. Promotion needs one hold-out run (2025-01-01 to 2026-07-10, `--holdout`), done once at the end.

## If it passes
1. One hold-out run of `short_only` (with the PM's go-ahead), with the same bar.
2. If that holds, run the short-only rule in shadow mode next to the live rule for a few weeks.
3. The PM decides; the live change would be one line in `configs/paper.toml` (`[signal] long_band`, or a router that never picks long), recorded in `docs/decisions/`.

## Changes
