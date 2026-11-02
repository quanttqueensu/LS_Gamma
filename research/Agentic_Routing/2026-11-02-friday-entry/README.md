# Hypothesis: on the stress-sized put book, opening new puts only on Fridays beats opening them on any day

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-friday-entry` (config: `configs/experiments/2026-11-02-friday-entry.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` book, allowing new puts only on Fridays (so a book closed midweek by its profit-take or stop waits for Friday to re-enter) earns more net P&L than re-entering the next day, at 1x and 2x spreads, over the full window and in each half, without a worse 5% expected shortfall or a drawdown beyond the stress budget.

## Why it matters for the desk
The 2026-10-31 strategy research found that the one-contract `always25` book earned essentially all of its mark-to-market P&L from Friday 10:15 to Tuesday 10:15, in line with Jones & Shemesh (2018) on option returns over weekends. The PM first asked to roll on Fridays instead of at 7 DTE, but the book already rolls on Fridays: 135 of the `hedged` book's 147 time exits are on a Friday, because 7 days before a Friday expiry is a Friday. The PM chose instead to test Friday-only re-entry: 44 of the `hedged` book's 182 entries were midweek, after a profit-take or stop. If waiting for Friday helps, it is one research switch to promote.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-31 strategy research report's check on the registered `always25` runs (2014-2024), and the book is the 2026-10-22 primary, chosen after its results. Before pre-registration, Claude tested this card's reporting code on the registered reference runs and so saw, for the `hedged` book: entries and time exits by weekday (used to design this card), and its net P&L by 10:15-to-10:15 interval (Friday to Monday +$51k, Monday to Tuesday +$58k, Thursday to Friday −$17k at 1x). This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **New research switch** `[backtest] entry_weekdays` (default `[]`, any day): new entries only on the listed weekdays (Monday = 0). Exits, stops and hedges are unchanged. A blocked day is logged as a `weekday` event.
- **Variants:**
  - `friday` (primary): `entry_weekdays = [4]`. A midweek profit-take or stop leaves the book flat until Friday. If Friday is a holiday, the book waits a week.
  - `tuesday_roll` (sensitivity): `[exit] exit_dte = 3`. The expiring put is held through the weekend and closed on the Tuesday of expiry week, and the new put is opened that day. No new code.
- **Also reported, not part of the bar:** entries by weekday, days flat, net P&L by 10:15-to-10:15 interval.
- **Trials:** 2 variants × 2 multiples = 4.

## Metric and pass bar
Primary `friday` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. 5% expected shortfall of daily P&L is no worse than 1.10 × the reference's (tail guard);
5. The maximum drawdown is at most $87,500, the 35% stress budget.

**Event floor:** `friday` must have at least 25 Monday-to-Thursday profit-take or stop exits at 1x (each one starts a wait); otherwise INCONCLUSIVE. 25 is the size below which a difference of a few trades decides the result.

**Hold-out bar** (only if it passes, and only when the PM asks): `friday` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (full-window net P&L higher, ES within 1.10x, maximum drawdown at most $87,500). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs the entry-day rule in the runner.

## Changes
