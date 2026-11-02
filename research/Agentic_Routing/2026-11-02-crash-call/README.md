# Hypothesis: a small long call when VIX/VIX3M ≥ 1.1 cuts the put book's drawdown and tail

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-crash-call` (config: `configs/experiments/2026-11-02-crash-call.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (max drawdown $70,998 vs $70,362 at 1x, $76,514 vs $75,488 at 2x) |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` put book, also buying at-the-money calls with 0.5% of capital ($1,250) whenever VIX/VIX3M at the prior close is at or above 1.1, held 5 trading days and delta-hedged with the book, makes the maximum drawdown and the 5% expected shortfall of daily P&L less severe, while net P&L stays no more than $10,000 below the `hedged` book, at 1x and 2x spreads.

## Why it matters for the desk
The 2026-10-07 strategy research on shock or regime triggers for long gamma found that long gamma pays, if anywhere, in a handful of crash episodes when the VIX curve inverts. The best condition fired about 7 days a year. It suggested a long-gamma trade on inverted-curve days only as a crash pair for the short-gamma book (risk management, not alpha), using a fast, market-implied trigger (VIX/VIX3M) rather than a slow regime model. The `hedged` put book's worst stretch is the 2018-2020 drawdown ($70.4k at 1x), and its profit depends on two March 2020 entries. A small delta-hedged long call that is on only when the curve inverts would be long gamma exactly when the short put is most exposed.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-07 report and from the 2026-10-22 `hedged` results (its drawdown and March 2020 concentration), both on 2014-2024. Before pre-registration, Claude counted how often the gate would fire from the features file (no backtest runs): VIX/VIX3M ≥ 1.1 at the close on 50 days in 12 episodes from 2014 to 2024 (24 of them in 2020, 16 in 2018); ≥ 1.0 on 193 days in 64 episodes. Claude also tested this card's reporting code on the registered `hedged` runs, whose headline numbers were already known. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500). The crash call is not counted in this stress test.
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live for the put.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration).
- **New research switches** (`[backtest]`, all off by default; commit a2d5334):
  - `crash_gate`: at the 10:15 decision, if VIX/VIX3M at the prior close is at or above this and no crash call is open, buy an at-the-money call.
  - `crash_dte = [min, target, max]`: the call's expiry window, chosen like the desk's entry rule (the Friday expiry closest to the target inside the window).
  - `crash_days`: the call is closed after this many trading days (`crash_time`), or at expiry. It has no stop, profit-take, flip or flat exit. If the gate is still on after it closes, a new call is bought at the same step.
  - `crash_premium`: contracts = floor(this share of the $250k capital / (fill price × 100)).
  - The call does not take the put's position slot. Its delta joins the book's daily 10-share hedge. One crash call at a time.
- **Variants:**
  - `crash11` (primary): gate 1.1; DTE 8-14, target 10; 5 trading days; 0.5% of capital ($1,250) per call.
  - `crash10` (sensitivity): gate 1.0, otherwise as `crash11`.
  - `crash11_30d` (sensitivity): DTE 21-45, target 30 (the desk's usual long call), otherwise as `crash11`.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET, exits at the `[schedule]` times.
- **Also reported, not part of the bar:** crash calls per year, net P&L of the crash calls and of the puts separately (round trips paired by entry time and contract), and drawdown curves against `hedged`.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `crash11` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. The maximum drawdown is less severe (smaller in absolute value);
2. The 5% expected shortfall of daily P&L is less severe;
3. Net P&L over the full window is not below the reference's minus $10,000.

**Event floor:** `crash11` must open at least 10 crash calls at 1x; otherwise INCONCLUSIVE. Ten is the fewest at which the call's effect on the tail is more than one or two episodes. The P&L allowance of $10,000 is about 8% of the reference's 1x P&L: the price the desk would pay for a smaller drawdown.

**Hold-out bar** (only if it passes, and only when the PM asks): `crash11` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the same three checks (all full-window). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs a second position type in the runner (the crash call beside the put), the gate, and its own exit.

## Changes
- 2026-11-02: run once (6 trials; registry rows tagged `3568520-dirty` because other cards of the same batch had uncommitted files in the shared working tree; the engine, configs and this card's files were unchanged). The pass bar above was not changed. Verdict: failed at 1x and 2x. Max drawdown was worse ($70,998 vs $70,362 at 1x, $76,514 vs $75,488 at 2x); ES 5% was less severe (−$2,998 vs −$3,016, −$3,077 vs −$3,094) and net P&L was within the $10k allowance ($119,806 vs $121,482, $98,891 vs $101,172). 14 crash calls met the floor of 10. See `summary.md` and `2026-11-02-crash-call.pdf`.
- 2026-11-02 (reporting only, after the run): `report.round_trips` matches closes to opens by time alone, which misassigns side and entry date when the put and a crash call open at the same 10:15 step. The engine also splits the book's hedge shares across open positions, so a single round trip's P&L includes shares inherited from the other leg. The script's charts were therefore changed to measure the call by the equity difference against `hedged`: the by-reason chart became `vs_hedged.png`, and the crash-call P&L panel became net P&L minus `hedged`. Rebuilt with `--report-only` (no trials). Pass-bar metrics come from the equity curve and are unaffected.
- 2026-11-02 (checker, after the run): the call is held 5 weekdays, not 5 trading days (`engine.crash_exit` counts business days without holidays); 3 of 14 `crash11` calls were held 4 trading days. Disclosed in the report and summary; no rerun. Reporting-only change also disclosed: the `split()` / `legs.csv` columns now give calls, contracts, premium, option net and marginal P&L instead of per-leg round trips.
