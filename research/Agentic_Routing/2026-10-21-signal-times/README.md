# Hypothesis: running the signal every hour, instead of once at 10:15, makes more entries

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-21-signal-times` (config: `configs/experiments/2026-10-21-signal-times.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | passed (entries-only bar; net P&L worse, not promoted) |
| **Started** | 2026-10-21 |

## Hypothesis
Running the full daily loop (signal, exits, entry, delta hedge) every hour from 10:15 to 15:15 ET, instead of once at 10:15, makes more entries over 2014-06 to 2024-12 and in each half, at 1x and 2x spreads, without worsening the daily tail by more than 10%.

A second question is answered by two sensitivity variants: does running once a day at a different time (12:45 or 15:45) instead of 10:15 make more entries?

## Why it matters for the desk
The book holds at most one position, and the signal is read once a day. Once a position closes, the desk waits until the next morning to look again, and an intraday move in implied volatility that crosses a band is missed. If more runs give more entries, the live runner could be scheduled several times a day (it allows one run today).

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the question comes from the PM, after the 2026-10-16 to 2026-10-18 experiments on this window. The run schedule itself has never been varied.

## Method
- **Book:** the current paper rules (`configs/paper.toml`, both sides, ATM, 1-share hedge threshold). Only `[schedule]` changes. No new engine code.
- **Signal:** the GARCH forecast uses completed days only, so it is the same at every run of a day. Only the ATM implied volatility, read from the snapshot at each run, changes during the day. Each run decides on data 15 minutes old and fills on trades in the next 15 minutes, as in the baseline. Spot comes from put-call parity on the 30-minute grid (10:15 to 15:45).
- **What a run does:** at each scheduled time the engine checks exits (time, stop, profit, flip, flat), enters if no position is open and the signal is long or short, then delta-hedges. This is what the live runner would do if it ran hourly. So the hourly variant also hedges six times a day, and stops are checked six times a day. The 3-day flat exit counts days (last signal of each day), as now.
- **Variants:**
  - `hourly` (primary): `signal = hedge = ["10:15", "11:15", "12:15", "13:15", "14:15", "15:15"]`.
  - `midday` (sensitivity): `signal = hedge = ["12:45"]`.
  - `close` (sensitivity): `signal = hedge = ["15:45"]`.
- **Comparison:** the registered baseline (trial 1, 10:15 once a day): 131 round trips, −$2,060 net at 1x, −$4,122 at 2x.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order; 6 trials.

## Metric and pass bar
Entries are counted as round trips (`trades` in the report table, counted by exit date; the last development position is closed by the embargo, so every entry has a close). Primary `hourly` against the baseline. Every check must hold at **both 1x and 2x**:
1. More round trips over the full window;
2. More round trips in 2014-06 to 2019-12;
3. More round trips in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 × the baseline's over the full window.

**Event floor:** none. Entries are what is measured.

**Secondary (reported, not the verdict):** the same four checks applied to `midday` and `close` answer the single-time question.

**Hold-out bar** (only if it passes, and only when the PM asks): `hourly` against the hold-out baseline over 2025-01-01 to 2026-07-10, at 1x and 2x: more round trips and |ES 5%| within 1.10x.

Reported, not part of the bar (the PM chose an entries-only bar): net P&L against the baseline, entries per year, entries and exits by run time, exits by reason (flips may fire more often intraday), hedge orders and commissions.

## If it passes
Run the hold-out once. If it holds: shadow mode next to the live rules, a decision record, then a live change. The live runner rejects more than one run a day (`runner.check_schedule`), so promotion needs a reviewed code change there and a scheduler, not only a `paper.toml` line.

## Changes
- 2026-10-21: run once (6 trials, commit 2784f7c). The pass bar above was not changed. Verdict: passed (225 vs 131 round trips; ES inside the guard). Net P&L worse (−$3,848 vs −$2,060 at 1x). Secondary: `midday` and `close` failed. See `summary.md` and `2026-10-21-signal-times.pdf`.
