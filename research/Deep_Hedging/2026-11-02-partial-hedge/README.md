# Hypothesis: hedging half the delta of high-VRP puts, at full size, beats always hedging

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-partial-hedge` (config: `configs/experiments/2026-11-02-partial-hedge.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, hedging only 50% of a put's delta for its whole life when VRP at entry (ATM IV minus the GARCH forecast) is above 2 vol points, while keeping the hedged book's full stress size, earns more net P&L than always hedging. This must hold at 1x and 2x spreads, over the full window and in each half, with a higher Sharpe ratio and a maximum drawdown within $87,500.

## Why it matters for the desk
The 2026-11-02 `vrp-hedge` card left high-VRP puts fully unhedged and failed, for two reasons:
- **The timing worked in the delta leg.** In the always-unhedged 2026-10-22 book, the put's delta earned 64% a year per dollar of delta for puts entered above 2 VRP points, against 9.5% for the rest.
- **It lost on sizing and one path.**
  - An unhedged put gets no hedge credit in the stress test, so it was smaller: 17.5 contracts against 25.2.
  - One unhedged put stopped out on 9 March 2020, three trading days before the hedged book's, and the book missed the 13 March entry.

This card keeps the hedged book's size and changes only the hedge, so it isolates the timing. It also keeps half the hedge, which limits how much share exposure one crash can add.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the 2026-11-02 `vrp-hedge` results and the 2026-10-22 card's results (2014-2024), so it is not an out-of-sample hypothesis.
  - Before pre-registration, Claude saw all of `vrp-hedge`'s results, including its sensitivity `vrp1` (1-point cutoff, fully unhedged), which beat the hedged book on every check.
  - This card's report code was tested only on the registered reference runs (`hedged`, and `vrp-hedge/vrp2`), with no new runs.
  - This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500), counting the 10-share band as unhedged.
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **New research switch:** `[backtest] vrp_hedge_cut` and `vrp_hedge_ratio`, both default 0 and off.
  - A put entered when VRP is above `vrp_hedge_cut` has its hedge target multiplied by `vrp_hedge_ratio` for its whole life. Puts entered at or below it are hedged in full.
  - VRP is the signal's value at the 10:15 decision (15-minute-old chain, GARCH forecast on completed days).
- **Size is kept at full hedged size (the PM's choice).** A partly hedged put is sized as if fully hedged.
  - The stress test therefore ignores the extra unhedged delta: half of the put's delta for `half2`, all of it for `none2`.
  - A one-day 20% drop can then cost a partly hedged put more than the 35% budget. The drawdown check below is the guard.
- **Variants:**
  - `half2` (primary): cut 2 vol points (the live short band), ratio 0.5.
  - `none2` (sensitivity): cut 2 points, ratio 0, so no hedge at full size.
  - `half1` (sensitivity): cut 1 point, ratio 0.5.
- **Context, not part of the bar:** the registered `2026-11-02-vrp-hedge/vrp2` runs (fully unhedged above 2 points, at unhedged size).
- **Also reported:**
  - the delta-leg P&L of partly and fully hedged puts within `half2`: the snapshot delta at each 10:15 decision times the spot change to the next decision, an attribution only;
  - net P&L per contract by VRP at entry;
  - partly hedged entries per year.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `half2` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window.
2. Net P&L is higher in 2014-06 to 2019-12.
3. Net P&L is higher in 2020-01 to 2024-12.
4. The Sharpe ratio of daily P&L is higher over the full window.
   - More equity exposure raises P&L mechanically, so P&L alone can't show the VRP timing works. The Sharpe check asks that it pays for its added variance.
   - This replaces the usual 1.10x ES guard, because a partial hedge adds daily variance by design.
5. The maximum drawdown is at most $87,500, the 35% stress budget.

**Event floor:** `half2` must have at least 20 round trips entered with a partial hedge at 1x (event `partial`); otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `half2` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (full-window net P&L higher, Sharpe higher, maximum drawdown at most $87,500). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds:
1. shadow mode;
2. a decision record;
3. live changes reviewed by the PM. Live needs the VRP check at entry and a per-position hedge ratio in the hedger.

## Changes
