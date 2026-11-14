# Hypothesis: a minimum-variance (vega-adjusted) hedge cuts the put book's tail without costing P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-mv-hedge` (config: `configs/experiments/2026-11-02-mv-hedge.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Gabe Soler (PM) |
| **Status** | failed (P&L $104,049 / $79,425 vs $121,482 / $101,172; tail and drawdown passed) |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, hedging each put to its delta plus a Hull-White-style vega term (vega × spot-vol beta / spot) makes the 5% expected shortfall of daily net P&L and the maximum drawdown less severe, with full-window net P&L no more than $5,000 below always hedging to delta, at 1x and 2x spreads.

## Why it matters for the desk
The 2026-09-27 leverage-effect report found that implied vol rises when SPY falls, so a delta hedge that holds IV fixed is biased for SPY options (Ruf & Wang; Hull & White). A short put hedged to its Black-Scholes delta still carries hidden long-SPY exposure through its short vega: in a selloff it loses through gamma and vega at once. The minimum-variance delta adds that exposure to the hedge. If it works, the put book's worst days get smaller at little cost, which is the book's main weakness (two March 2020 entries made 54% of its profit, and its drawdown was $70k).

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-09-27 leverage-effect report (literature), not from this book's results. The book is the 2026-10-22 primary, chosen after its 2014-2024 results. Before pre-registration, the desk tested this card's reporting code on the registered `hedged` reference run and on the features file. That showed:
  - the median spot-vol beta over the window (about −142 VIX points per unit SPY return, so a 1% fall goes with about 1.4 VIX points up);
  - that the helpers run.

  No P&L or tail numbers of the reference were printed in that test. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **New research switch** `[backtest] mv_hedge = k` (default 0, off).
  - Each put's hedge target becomes its delta target plus k × vega × β / S × contracts × 100, with the position's sign.
  - Vega is the chain's vega per vol point; S is the parity spot.
  - β is the slope of a regression of daily VIX-point changes on SPY daily returns, over the trailing 252 completed days (prior closes only, refit each day).
  - For a short put β is negative, so the hedge sells more shares than the delta alone.
  - Sizing is unchanged: the stress test still uses the delta hedge.
- **Variants:**
  - `mv` (primary): k = 1, the full term.
  - `mv_half` (sensitivity): k = 0.5.
- **Approximations, disclosed:**
  - VIX stands in for the change in the put's own IV: a 25-delta put's IV may move more or less than VIX.
  - The term is a walk-forward spot-vol beta, not Hull & White's fitted a, b, c coefficients.
  - Stops and the profit-take include hedge P&L, so a different hedge can change when positions close and the path after.
- **Also reported:** the beta over time, short shares per open contract by year, the 40 worst days, and round trips matched by entry time with the reference.
- **Trials:** 2 variants × 2 multiples = 4.

## Metric and pass bar
Primary `mv` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. The 5% expected shortfall of daily net P&L is less severe over the full window;
2. The maximum drawdown is less severe over the full window;
3. Full-window net P&L is not below the reference's minus $5,000.

The tail and the drawdown are the targets. The P&L check allows a small cost, about 4% of the reference's 1x P&L, for the extra hedge.

**Event floor:** `mv` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `mv` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the same three full-window checks. This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then a new hedger in `core/Algos/Hedging/` with its own `target_shares()` (the `new-hedger` skill), reviewed by the PM.

## Changes
- 2026-11-02: run once (4 trials, pre-registration commit 3ab834b). The registry tags the `mv` 1x row 79b09a1-dirty and the other three 3568520-dirty: other cards of the same batch were pre-registered, and had uncommitted files in the shared working tree, during the run. The engine, `configs/backtest.toml` and this card's config, card and script are unchanged between 3ab834b and both tags. The pass bar above was not changed. Verdict: failed at 1x and 2x. ES 5% (−$2,828 / −$2,871 vs −$3,016 / −$3,094) and max drawdown ($41,112 / $41,119 vs $70,362 / $75,488) passed; net P&L ($104,049 / $79,425 vs $121,482 / $101,172) fell more than the $5,000 allowed. See `summary.md` and `2026-11-02-mv-hedge.pdf`.
