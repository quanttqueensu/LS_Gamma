# Hypothesis: tilting the put book's stress budget toward high-VVIX days beats a fixed budget

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-vvix-sizing` (config: `configs/experiments/2026-11-02-vvix-sizing.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (drawdown $106.6k > $87.5k; ES 1.19x; 2014-19 at 1x) |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, scaling each entry's stress budget by 1 + 0.5 × (2 × VVIX's one-year percentile − 1), so from 0.5x on the calmest VVIX days to 1.5x on the most volatile, earns more net P&L than the fixed 35% budget, at 1x and 2x spreads, over the full window and in each half, without a worse 5% expected shortfall or a drawdown beyond $87,500.

## Why it matters for the desk
Park (2015) finds that a rise in VVIX raises the prices of S&P 500 puts and lowers their returns over the next three to four weeks, which favours the seller. VVIX is already in the live pipeline. The tilt keeps the average budget near 35% and moves size toward the days the literature says pay more. If it passes, sizing changes by one input.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-31 strategy research report (literature, not the desk's results), and the book is the 2026-10-22 primary, chosen after its results. VVIX tends to be high when IV is high, and that book's profit is concentrated in high-IV March 2020 entries, so a pass could partly repeat that concentration; the report will split P&L by multiplier tercile. Before pre-registration, Claude tested this card's reporting code on the registered reference runs and so saw, for the `hedged` book: its contracts per entry by year and the multiplier path chart, but not its P&L by multiplier. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **New research switches** `[backtest] size_by` (a feature column, default `""`) and `size_tilt` (default 0): the stress budget is multiplied by 1 + tilt × (2p − 1), where p is the percentile of the column's last completed close among its last 252 completed closes (the prior day's close, as live). VVIX is the frozen yfinance series in the snapshots' features.
- **Variants:**
  - `vvix` (primary): `size_by = "vvix"`, `size_tilt = 0.5`, so 0.5x to 1.5x of 35% (17.5% to 52.5% of capital).
  - `vvix_light` (sensitivity): tilt 0.25, so 0.75x to 1.25x.
  - `vvix_reverse` (sensitivity): tilt −0.5, larger when VVIX is low. If VVIX carries the information, this should do worse than the primary.
- **Also reported, not part of the bar:** the multiplier over time, contracts per entry, and per-contract P&L by multiplier tercile in the reference and the primary.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `vvix` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. 5% expected shortfall of daily P&L is no worse than 1.10 × the reference's (tail guard: larger size on some days must not buy P&L with tail);
5. The maximum drawdown is at most $87,500, the 35% stress budget.

**Event floor:** `vvix` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `vvix` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (full-window net P&L higher, ES within 1.10x, maximum drawdown at most $87,500). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs the VVIX percentile and the tilt in the runner's sizing.

## Changes
- 2026-11-02: run once (6 trials, commit 954824c). The pass bar above was not changed. Verdict: failed at 1x and 2x. `vvix` made +$145,183 / +$130,641 against +$121,482 / +$101,172, but its maximum drawdown was $106,599 / $110,464 (limit $87,500), its ES 1.19x / 1.17x (limit 1.10x), and 2014-2019 at 1x was $2,135 lower. Five entries in February to April 2020, all sized at 1.39x-1.5x, gave 45% of the lead. The two `vvix_reverse` rows are tagged `-dirty` because other experiments' new figure folders were in the shared working tree; code and configs were unchanged. See `summary.md` and `2026-11-02-vvix-sizing.pdf`.
- 2026-11-02 (after the run): chart-only fix in `experiment.py`. The yearly chart's legend moved to the upper left, clear of the bars. Figures rebuilt with `--report-only`; no new trials.
