# Hypothesis: on the stress-sized put book, selling a 20-delta put instead of a 25-delta put raises net P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-lower-delta` (config: `configs/experiments/2026-11-02-lower-delta.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, selling the 20-delta put instead of the 25-delta put earns more net P&L at 1x and 2x spreads, over the full window and in each half, without a 5% expected shortfall more than 1.10 times worse or a drawdown beyond the stress budget.

## Why it matters for the desk
The 2026-10-22 deep research (Card A) recommended selling a front-month put at 15-25 delta and testing 15- and 20-delta against the registered 25-delta book. That test was never run.

The desk has tested only 25-delta, 35-delta and ATM puts. In 2026-10-17, 25-delta beat ATM and 35-delta, mostly because it pays less in spreads and commissions.

The stress budget changes the trade-off:
- A lower-delta put loses less in the stress test, so the book holds more contracts.
- Each contract collects less premium.
- More contracts cost more in commissions and spread.

Whether that nets out positive is an open question. If it is, the change is one number in the live strike selection.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the 2026-10-22 deep research, which was written after the desk's 25-delta, 35-delta and ATM results on 2014-2024. The book is the 2026-10-22 primary, chosen after its results. Before pre-registration, Claude tested this card's reporting code on the registered reference runs and so saw, for the `hedged` book at 1x:
  - 182 round trips, with median 24 and maximum 100 contracts;
  - net $24.5 per contract per round trip (pooled);
  - $8.8k of commissions and about $20k of spread paid.

  This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily with a 10-share band.
  - The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the batch's new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads.
  - Costs: $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed).
  - Schedule: decisions and hedges once a day at 10:15 ET.
- **Strike:** the listed put whose delta is closest to the target, on the expiry closest to 30 DTE within 21-45 DTE (existing switch `[backtest] put_delta`). No new code.
- **Variants:**
  - `put20` (primary): `put_delta = 0.20`;
  - `put15` (sensitivity): `put_delta = 0.15`.
- **Also reported, not part of the bar:**
  - net P&L per contract per round trip;
  - contracts per entry;
  - commissions, and the spread paid (estimated as the gross P&L lost going from 1x to 2x spreads).
- **Trials:** 2 variants × 2 multiples = 4.

## Metric and pass bar
Primary `put20` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window.
2. Net P&L is higher in 2014-06 to 2019-12.
3. Net P&L is higher in 2020-01 to 2024-12.
4. **Tail guard:** the 5% expected shortfall of daily P&L is no worse than 1.10 × the reference's.
5. The maximum drawdown is at most $87,500, the 35% stress budget.

**Event floor:** `put20` must have at least 30 round trips at 1x; otherwise the result is INCONCLUSIVE. The reference has 182, so the floor only catches a broken run.

**Hold-out bar** (only if it passes, and only when the PM asks): `put20` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above:
- full-window net P&L higher;
- ES within 1.10x;
- maximum drawdown at most $87,500.

This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
1. Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`.
2. If it holds: shadow mode, then a decision record.
3. Then live changes, reviewed by the PM. Live needs a delta target in `selection.pick_strike`.

## Changes
