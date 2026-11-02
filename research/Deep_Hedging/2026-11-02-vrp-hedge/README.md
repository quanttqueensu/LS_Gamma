# Hypothesis: leaving puts unhedged when VRP is high beats always hedging, at a better Sharpe

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-vrp-hedge` (config: `configs/experiments/2026-11-02-vrp-hedge.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (+$114,100 / +$87,924 vs +$121,482 / +$101,172) |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, leaving a new put unhedged for its whole life when VRP at entry (ATM IV minus the GARCH forecast) is above 2 vol points, and sizing it to the unhedged stress loss, earns more net P&L than always hedging, at 1x and 2x spreads, over the full window and in each half, with a higher Sharpe ratio and a drawdown within $87,500.

## Why it matters for the desk
In the 2026-10-22 card the `unhedged` book earned +$253.8k against +$121.5k hedged at 1x, and 75% of the unhedged P&L was the return on its option delta. Bollerslev, Tauchen & Zhou (2009) find that a high variance risk premium predicts high index returns, most strongly over a quarter. If the desk's VRP does the same, keeping the put's delta only when VRP is high should keep most of that equity return while hedging the rest of the time.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-22 card's results (2014-2024) and the 2026-10-31 strategy research report. Before pre-registration, Claude tested this card's reporting code on the registered reference runs and so saw, for the `hedged` book: the VRP distribution at entry (20% of entries above 2 vol points, used to choose the sensitivities with the PM). For the 2026-10-22 `unhedged` book it also showed net P&L per contract split at 2 vol points of VRP: $90 above and $22 below at 1x, from 58 and 354 round trips. That is the mechanism this card tests, seen on a reference book; it could not be unseen. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **New research switch** `[backtest] vrp_unhedge` (default 0, off): a put entered when VRP is above this level is never hedged (its hedge target is 0 shares), and it is sized with the unhedged stress loss (the full put loss in the crash, with no hedge gain), so every position stays within the 35% budget. Puts entered at or below it are hedged as in the reference. VRP is the signal's value at the 10:15 decision (15-minute-old chain, GARCH forecast on completed days).
- **Variants:**
  - `vrp2` (primary): `vrp_unhedge = 0.02`, the live short band. About 20% of the reference's entries.
  - `vrp1` (sensitivity): 0.01.
  - `vrp4` (sensitivity): 0.04, about 10% of entries.
- **Context, not part of the bar:** the registered 2026-10-22 `unhedged` book.
- **Also reported:** P&L of hedged and unhedged positions within each variant, unhedged entries per year, and the reference books' P&L per contract by VRP at entry.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `vrp2` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. The Sharpe ratio of daily P&L is higher over the full window. More equity exposure raises P&L mechanically, so P&L alone can't show the VRP timing works; the Sharpe check asks that it pays for its added variance. This replaces the usual 1.10x ES guard, because unhedged positions add daily variance by design;
5. The maximum drawdown is at most $87,500, the 35% stress budget.

**Event floor:** `vrp2` must have at least 20 round trips entered unhedged at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `vrp2` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (full-window net P&L higher, Sharpe higher, maximum drawdown at most $87,500). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs the VRP check at entry and a per-position hedge flag.

## Changes
- 2026-11-02: run once (6 trials, commit 954824c; the `vrp4` rows are tagged `-dirty` because the other three experiments of the batch were writing files in the same working tree, with no change to this experiment's code, config or engine). The pass bar above was not changed. Verdict: failed at 1x and 2x (`vrp2` net P&L $114,100 / $87,924 vs $121,482 / $101,172; Sharpe 0.51 / 0.39 vs 0.52 / 0.43). The sensitivity `vrp1` beat the reference on every check, but sensitivities cannot pass this card. See `summary.md` and `2026-11-02-vrp-hedge.pdf`.
- 2026-11-02 (after the run): chart-only fix in `experiment.py`: the commissions chart's x labels rotated so they don't overlap. Figures rebuilt with `--report-only`; no new trials.
