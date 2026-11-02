# Hypothesis: cutting the put book's size on calm-VVIX days (capped at 1x) beats a fixed budget on Sharpe and drawdown

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-vvix-cap` (config: `configs/experiments/2026-11-02-vvix-cap.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, scaling each entry's stress budget by min(1, 1 + 0.5 × (2 × VVIX's one-year percentile − 1)) gives a higher Sharpe ratio than the fixed 35% budget, over the full window and in each half, with a less severe maximum drawdown, at 1x and 2x spreads. The multiplier is 0.5x on the calmest VVIX days and 1x from the median up.

## Why it matters for the desk
The 2026-11-02 VVIX sizing card (0.5x-1.5x) made more P&L than the fixed budget but failed on drawdown ($106.6k against a $87.5k limit) and tail, because it sized up into March 2020. Its next step suggested a tilt capped at 1x: keep the size-down on calm VVIX, never size up. Park (2015) links high VVIX to lower later put returns, which favours the seller, so calm-VVIX days should be the weaker ones to sell on. A capped tilt can only make the book smaller, so the test is on risk-adjusted return, not raw P&L. That card's own evidence was weak: in the `hedged` book, mean net P&L per contract by VVIX tercile at entry was $5.7 (low), $25.7 (middle) and −$0.1 (high). The expected gain is small.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:**
  - The idea comes from the 2026-11-02 VVIX sizing results on 2014-2024, including the per-contract P&L by VVIX tercile above.
  - The book is the 2026-10-22 primary, chosen after its results.
  - Before pre-registration, Claude smoke-tested this card's tilt helper on the first five entry times of the registered `hedged` runs, so it saw five multiplier values (0.66x-1x) but no P&L. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within the stress budget (35% of capital, $87,500, before the tilt).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x; Sharpe 0.52 / 0.43; max drawdown $70,362 / $75,488), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Context, charts only:** the uncapped `2026-11-02-vvix-sizing/vvix` runs.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **Research switches:**
  - `[backtest] size_by` and `size_tilt` (from the VVIX sizing card): the budget is multiplied by 1 + tilt × (2p − 1). Here p is VVIX's percentile at the last completed close among its last 252 completed closes (the prior day's close, as live).
  - New `size_cap` (default 0 = none): the multiplier is capped at this value.
- **Variants:**
  - `vvix_cap` (primary): `size_by = "vvix"`, `size_tilt = 0.5`, `size_cap = 1.0`, so 0.5x to 1x of 35% (17.5% to 35% of capital).
  - `vvix_cap_light` (sensitivity): tilt 0.25, cap 1.0, so 0.75x to 1x.
- **Also reported, not part of the bar:**
  - the multiplier over time;
  - contracts per entry by year;
  - per-contract P&L by VVIX tercile at entry in the reference and the primary.
- **Trials:** 2 variants × 2 multiples = 4.

## Metric and pass bar
Primary `vvix_cap` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. The Sharpe ratio is higher over the full window;
2. The Sharpe ratio is higher in 2014-06 to 2019-12;
3. The Sharpe ratio is higher in 2020-01 to 2024-12;
4. The maximum drawdown is less severe (smaller in absolute value) than the reference's.

**Why these numbers:** a capped tilt can only shrink the book, so net P&L is expected to fall by construction. The claim is better P&L per unit of risk and a smaller drawdown, in both halves so that one episode can't carry it. This is the bar the PM approved for the risk-sizing cards in this batch.

**Event floor:** `vvix_cap` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `vvix_cap` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x. The checks are the full-window ones above: Sharpe higher and maximum drawdown less severe. This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs the VVIX percentile, the tilt and the cap in the runner's sizing.

## Changes
