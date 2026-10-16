# Hypothesis: on the short-only book, the VIX term gate cuts the daily tail without costing net P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-vix-gate-backtest` (config: `configs/experiments/2026-10-16-vix-gate-backtest.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-16 |

## Hypothesis
On the short-only book, skipping short entries when VIX/VIX3M >= 1 cuts the daily 5% tail by at least 20% while keeping net P&L at 1x and 2x.

## Why it matters for the desk
Two earlier cards tested this gate on a stand-in for P&L (IV minus next-month realized vol), not on option trades:
- [`2026-10-07-vix-term-gate`](../2026-10-07-vix-term-gate/README.md) failed its precision bar, but the gate removed the worst short outcomes (2020-02-28 among them).
- [`2026-10-07-vix-gate-tail`](../2026-10-07-vix-gate-tail/README.md) cut the 5% expected shortfall by 32% on unseen 2006-2015 data, but skipped 35% of short days, so it failed its days-kept rule.

Both summaries said the next step was real P&L: a short put with the live stops and daily hedging, priced from R2 option trades. This card is that test. The live short put already has a 1x-credit stop, which could cap the same tail losses on its own; the question is whether the gate still adds tail protection next to the stop, and what it costs in P&L. The short-only book (`2026-10-16-short-only`, passed in-sample) is the reference, so a pass would add the gate as the first rule in front of it in the router.

## Data
- R2 replay snapshots `v1` (`config_hash` b040760187f0), development window 2014-06-02 to 2024-12-31.
- VIX/VIX3M: the daily `vix_vix3m` column of the snapshot `features.parquet` (daily index closes, the same ratio the live pipeline builds in `pipeline/features.py`). It is populated on all 2,665 trading days of the development window (no gaps). The ratio is at or above 1.0 on 193 of those days and at or above 0.95 on 524 (index data only; no backtest results were looked at).
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the 2026-10-16 desk discussion of the baseline on this window (and from the two 2026-10-07 proxy cards, which used 2006-2025 index data that overlaps this window). A pass is in-sample evidence. Promotion needs one hold-out run.

## Method
- **Book:** short-only (`[signal] long_band = -inf`) plus the gate; otherwise the live `configs/paper.toml` rules: a short put near 30 DTE, 1 contract, `max_positions = 1`, signal and delta hedge at 10:15 ET, the 3-day flat exit, the 7-DTE time exit, the 1x-credit stop and the 50% profit-take. Costs: $0.65 per contract, $0.005 per share, $1 minimum per order, fills at the modelled half-spread times the multiple.
- **The gate (research-only engine flag `[backtest] short_gate`, default 0 = off):** before a short entry, if `short_gate > 0` and the last completed day's `vix_vix3m` (the row dated before the decision day, i.e. yesterday's close, known at 10:15 ET; no look-ahead) is >= `short_gate`, the entry is skipped and a `gate` event is logged with the ratio. A missing ratio means no gate. It gates entries only: a short that is already open keeps its normal exits. While the curve stays inverted, the gate blocks every new short; the first signal day after it normalises enters as usual.
- **Variants:**
  - `gate1` (primary): `[backtest] short_gate = 1.0`.
  - `gate095` (sensitivity, reported only): `[backtest] short_gate = 0.95`.
- **Reference:** the already-registered runs of `2026-10-16-short-only/short_only` at 1x and 2x (net P&L -$773.80 and -$2,351.35). They are not rerun: with the gate off the current engine reproduces that run's 1x equity exactly. Baseline trial 1 (live rules) is shown in the charts for context.
- **Runs:** each variant at 1x and 2x spreads: 4 new trials.
- **Charts beyond the standard set:** gate-blocked days per year; VIX/VIX3M over time with gated days marked; net P&L of the reference's round trips grouped by whether their entry day would have been gated (aggregates only).
- Run: `PYTHONPATH=src python research/Agentic_Routing/2026-10-16-vix-gate-backtest/experiment.py` (`--report-only` rebuilds from registered runs, no new trials).

## Metric and pass bar
Primary `gate1` against reference `short_only` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. |ES 5% (daily)| of `gate1` is no more than 0.80 x the reference's |ES 5%| over the full window (a cut of at least 20%, the hypothesis);
2. |ES 5%| of `gate1` is smaller than the reference's in 2014-06 to 2019-12;
3. |ES 5%| of `gate1` is smaller than the reference's in 2020-01 to 2024-12 (so the cut is not one episode);
4. Net P&L of `gate1` is at least the reference's over the full window (`not_below`, allowed shortfall $0: "keeping net P&L").

This bar differs from the standard one because the tail is the target: ES is the main test and P&L is the guard. The 20% cut is the PM's number. The proxy cards found about a third, and stops on real puts may already take part of it, so 20% is a meaningful but not extreme bar.

**Event floor:** the gate must block short entries on at least 10 distinct days in `gate1` at 1x (counted from `gate` events by date). Otherwise it fired too rarely to judge and the result is INCONCLUSIVE. The gate can only fire on days with a short signal, an empty book and an inverted curve, so it fires on far fewer than the 193 inverted days.

**Hold-out bar** (only if it passes, and only when the PM asks): `gate1` against the hold-out baseline (live rules) over 2025-01-01 to 2026-07-10, at 1x and 2x. Net P&L must be higher, and |ES 5%| no more than 1.10 x the baseline's.

## If it passes
Combine it with the other passing rules (short-only first) into one candidate. Run the hold-out once on that combination, then shadow mode with the gate as a `SIGNALS` wrapper around `vrp_band`, then a decision record, then the one-line change in `configs/paper.toml`.

## Changes
