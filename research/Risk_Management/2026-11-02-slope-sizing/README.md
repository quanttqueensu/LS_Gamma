# Hypothesis: tilting the put book's stress budget toward steep-contango days beats a fixed budget

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-slope-sizing` (config: `configs/experiments/2026-11-02-slope-sizing.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (P&L lower at 1x and 2x; risk lower) |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, scaling each entry's stress budget by 1 − 0.5 × (2 × VIX/VIX3M's one-year percentile − 1), so from 1.5x in the steepest contango to 0.5x at the most inverted, earns more net P&L than the fixed 35% budget, at 1x and 2x spreads, over the full window and in each half, without a worse 5% expected shortfall or a drawdown beyond $87,500.

## Why it matters for the desk
Johnson (2017) finds that the VIX term-structure slope predicts returns on S&P 500 variance swaps, VIX futures and straddles beyond other VRP proxies: a steeper upward slope predicts lower returns to holding variance, so better returns to selling it. The desk has used the VIX curve only as a gate that skips shorts, which failed twice (2026-10-07-vix-term-gate and 2026-10-16-vix-gate-backtest). This card uses it to size instead.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-31 strategy research report (literature), and the book is the 2026-10-22 primary, chosen after its results. The desk's earlier gate tests showed that skipping shorts on an inverted curve removed profit, and the 2026-10-22 book made most of its profit from entries in March 2020, when the curve was inverted. Both point against this card's direction; the direction is fixed by the literature, not by those results. Before pre-registration, Claude tested this card's reporting code on the registered reference runs and so saw, for the `hedged` book: its contracts per entry by year and the multiplier path chart, but not its P&L by multiplier. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **New research switches** `[backtest] size_by` and `size_tilt`, as in `2026-11-02-vvix-sizing`. The column is `vix_vix3m` (VIX / VIX3M from the snapshots' features; below 1 is contango, above 1 inverted), lagged to the prior close.
- **Variants:**
  - `slope` (primary): `size_by = "vix_vix3m"`, `size_tilt = -0.5`, so 1.5x when VIX/VIX3M is at its one-year low (steepest contango) and 0.5x at its one-year high.
  - `slope_light` (sensitivity): tilt −0.25, so 0.75x to 1.25x.
  - `slope_reverse` (sensitivity): tilt +0.5, larger when the curve is flat or inverted. If the literature's direction is right, this should do worse than the primary.
- **Also reported, not part of the bar:** the multiplier over time, contracts per entry, and per-contract P&L by multiplier tercile in the reference and the primary.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `slope` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. 5% expected shortfall of daily P&L is no worse than 1.10 × the reference's (tail guard);
5. The maximum drawdown is at most $87,500, the 35% stress budget.

**Event floor:** `slope` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `slope` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (full-window net P&L higher, ES within 1.10x, maximum drawdown at most $87,500). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs the VIX/VIX3M percentile and the tilt in the runner's sizing.

## Changes
- 2026-11-02: run once: 6 trials, at branch head 954824c. That commit adds only another card's pre-registration after c74f769. The two `slope_reverse` rows are tagged `-dirty` because a parallel experiment's reporting script was being edited during the run; the engine, configs and this card's files were unchanged. The pass bar above was not changed. Verdict: failed on all six P&L checks (`slope` $100,574 / $78,318 against `hedged` $121,482 / $101,172 at 1x / 2x); the ES and drawdown checks passed (maximum drawdown $42,017 / $46,035). Average contracts per entry were unchanged (24.7 against 25.4), but the early-2020 entries were cut to 0.5-0.67x, which cut the March 2020 winners by about 40%. See `summary.md` and `2026-11-02-slope-sizing.pdf`.
