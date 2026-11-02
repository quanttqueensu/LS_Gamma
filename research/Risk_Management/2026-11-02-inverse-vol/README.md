# Hypothesis: tilting the put book's stress budget away from high-VIX days beats a fixed budget on Sharpe and drawdown

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-inverse-vol` (config: `configs/experiments/2026-11-02-inverse-vol.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, scaling each entry's stress budget by 1 − 0.5 × (2 × VIX's one-year percentile − 1), so from 1.5x when VIX is at its one-year low to 0.5x at its one-year high, gives a higher Sharpe ratio than the fixed 35% budget over the full window and in each half, with a less severe maximum drawdown, at 1x and 2x spreads.

## Why it matters for the desk
The 2026-10-22 deep research proposed sizing the always-on put by 1/VIX or 1/GARCH, capped by the budget (its Card B), and it has never been run. The 2026-10-22 book's weakness is concentration: two March 2020 entries (100 and 71 contracts, IV above 45%) gave 54% of its round-trip profit. The stress rule sizes up into high IV, because a richer put loses less in the stress scenario per dollar of premium. This card partly reverses that. It judges risk-adjusted sizing on Sharpe and drawdown, not raw P&L, because a book that is smaller when VIX is high is expected to make less in a crash rally.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-22 deep research (literature and desk reasoning). The book is the 2026-10-22 primary, chosen after its results. Earlier cards on the same book are related: `2026-11-02-slope-sizing` (sizing down on an inverted VIX curve) gave a higher Sharpe (0.64 against 0.52) but lower P&L, and `vvix_reverse` (sizing down when VVIX is high) gave a Sharpe of 0.55. Those results suggest this direction raises Sharpe; the bar was set knowing them. This card's variants have no runs yet, and Claude did not run this card's reporting code on the reference before pre-registration.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x; Sharpe 0.52 / 0.43; maximum drawdown $70,362 / $75,488), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **Research switches:** `[backtest] size_by` and `size_tilt` (from `2026-11-02-vvix-sizing`), and `size_cap` (new in this batch: the multiple is capped at this value). The percentile is over the last 252 completed days, at the prior close.
- **This is a rank version of 1/VIX, not a literal ratio:** the multiple depends on where VIX sits in its own one-year range, so it averages about 1x and is bounded at 0.5x and 1.5x.
- **Variants:**
  - `vix_inv` (primary): `size_by = "vix"`, `size_tilt = -0.5`, so 1.5x at VIX's one-year low and 0.5x at its high.
  - `vix_inv_cap` (sensitivity): the same with `size_cap = 1.0`, so 0.5x to 1x and never above the budget. This is the deep research's "capped by the budget" version.
  - `rv_inv` (sensitivity): `size_by = "rv_m"` (monthly realized volatility), tilt −0.5, a stand-in for sizing by 1/GARCH.
- **Also reported, not part of the bar:** the multiplier over time, contracts per entry by year, and per-contract P&L by multiplier tercile in the reference and the primary.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `vix_inv` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. The Sharpe ratio is higher over the full window;
2. The Sharpe ratio is higher in 2014-06 to 2019-12;
3. The Sharpe ratio is higher in 2020-01 to 2024-12;
4. The maximum drawdown is less severe than the reference's.

**Event floor:** `vix_inv` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `vix_inv` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (Sharpe higher, maximum drawdown less severe). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs VIX's one-year percentile and the tilt in the runner's sizing.

## Changes
