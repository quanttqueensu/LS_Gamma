# Hypothesis: selling 25-delta puts instead of ATM puts raises net P&L on the best book

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-17-otm-put` (config: `configs/experiments/2026-10-17-otm-put.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-17 |

## Hypothesis
On the short-only book with the 10-share hedge band, selling a put near 25 delta instead of the ATM put raises net P&L at 1x and 2x spreads, over the full window and in each half, without a worse daily tail, because out-of-the-money index puts carry more volatility premium per unit of risk (the skew).

## Why it matters for the desk
After 12 option-P&L experiments, every book still loses money after costs at 2x spreads. Timing, exits, sizing and forecasting changes moved little; the edge before costs is thin. Research on index options (e.g. Coval and Shumway 2001, "Expected Option Returns"; Bondarenko 2014, "Why Are Put Options So Expensive?") finds the premium is largest in out-of-the-money puts. If the desk's structure is selling the wrong strike, this is the change that could flip the sign.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the PM's discussion of all 2026-10-16 results on this window; the strike choice itself has never been varied before.
- **Feasibility (inputs only, checked on 257 sampled 10:15 snapshots):** on the chosen ~30-DTE expiry the nearest-to-25-delta put has |delta| 0.24-0.26 (5th-95th percentile), sits a median 3.1% below spot, and costs a median 47% of the ATM put. Marks come from the per-expiry smile fit (|ln K/F| up to 0.15), which covers these strikes.

## Method
- **Book:** the best book so far, short-only (`[signal] long_band = -inf`) with the 10-share hedge band (`[hedge] min_shares = 10`). Signal unchanged: VRP on the ATM IV of the chosen expiry against the GARCH forecast, short above +2 vol points.
- **New, research-only:** `[backtest] put_delta` (default 0 = ATM, as live). When set, the engine sells the put on the same expiry whose |delta| is closest to the target. Stops (1x credit), the 50% profit-take, the 3-day flat exit and the 7-DTE time exit are unchanged, so in dollars they scale with the smaller credit. Hedging targets the position's own delta, so the hedge is smaller.
- **Variants:** `put25` (primary, `put_delta = 0.25`) and `put35` (sensitivity, `put_delta = 0.35`, reported only).
- **Reference:** the registered runs of `2026-10-16-short-only-band10/band10` (−$170.43 at 1x, −$1,847.47 at 2x), reused, not rerun. Its strategy config is identical apart from `put_delta`. Baseline trial 1 is shown for context.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order; 4 trials. The default config was checked to reproduce baseline trial 1 exactly after the switch was added (engine called directly, not registered).

## Metric and pass bar
Primary `put25` against reference `band10` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. OTM puts are cheaper but lose more as a multiple of credit in a crash, so the tail guard matters.

**Event floor:** `put25` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE. The reference has 100.

**Hold-out bar** (only if it passes, and only when the PM asks): `put25` against the hold-out baseline over 2025-01-01 to 2026-07-10, at 1x and 2x: net P&L higher and |ES 5%| within 1.10x.

Reported, not part of the bar: whether the book is profitable outright, credit per trade, exits by reason (stops may fire more often on a smaller credit), and net P&L per round trip.

## If it passes
Run the hold-out once. If it holds: shadow mode next to the live rules, a decision record, then a live change. Strike selection is live code (`trading/selection.py`), so promotion also needs a code change there, reviewed by the PM.

## Changes
- (dated notes, if the plan had to change)
