# Hypothesis: on the short-only book, 45-DTE entries with a 21-DTE exit raise net P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-dte-45-21` (config: `configs/experiments/2026-10-16-dte-45-21.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-16 |

## Hypothesis
On the short-only book, entering near 45 DTE (min 35, max 60) and exiting at 21 DTE raises net P&L at 1x and 2x, in both halves, without a worse tail, compared with the live 30 DTE entry and 7 DTE exit.

## Why it matters for the desk
The live book sells a put near 30 DTE and holds it to 7 DTE at most, which is where gamma is highest and a short put is most exposed to a fast drop. A common practitioner rule is to sell near 45 DTE and close at 21 DTE, which avoids the last three weeks of high gamma. If it beats the live window on this book after costs, it is a three-line change to `[entry]` and `[exit]` in `configs/paper.toml`.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the 2026-10-16 desk discussion of the baseline on this same window, so a pass is in-sample evidence. Promotion needs one hold-out run.

## Method
- **Book:** short-only (`[signal] long_band = -inf`); otherwise the live `configs/paper.toml` rules. That means a short put on a Friday expiry, 1 contract, hedged daily at 10:15 ET. The 3-day flat exit, the stop (1x credit), the 50% profit-take and the 1-day stop cool-off stay as live.
- **Reference:** the registered runs of `2026-10-16-short-only/short_only` (same config as the short-only book, at 1x and 2x). They are reused, not rerun. Baseline trial 1 (live rules, long and short) is shown in the charts for context only.
- **Variants:**
  - `dte45` (primary): `[entry] target_dte = 45, min_dte = 35, max_dte = 60`; `[exit] exit_dte = 21`.
  - `dte45_exit14` (sensitivity, reported only): the same entry, `[exit] exit_dte = 14`.
- **Expiry choice on the replay chain** (`selection.pick_expiry`, unchanged): it takes the Friday expiry with DTE in [min_dte, max_dte] closest to target_dte, ties going to the shorter one. The replay chain lists expiries up to 60 DTE (`[history] max_dte = 60`), so 60 is the edge of the data and the cap never binds beyond what the chain holds. A pre-run check on every third trading day's 10:15 snapshot (867 snapshots, chain only, no results) found:
  - a Friday expiry in 35-60 DTE on every sampled snapshot (none missing);
  - the farthest listed Friday expiry has a median of 50 DTE (minimum 35), because expiries with too few trades for a smile fit are dropped;
  - the 45-DTE rule picks a median of 43 DTE (mean 43; 37-39 DTE on about 20% of snapshots, 49-60 DTE on about 6%), against a median of 30 DTE for the live rule.
- **What else moves with the window (part of the treatment):**
  - The VRP signal is measured on the picked expiry (`runner.decide`): ATM IV of the ~43-DTE expiry against a GARCH forecast over the same horizon, with the same 0.02 short band. So entry days and the 3-day flat exit can change too, not only the contract. This is what the one-line live change would do.
  - The pre-hold-out embargo is `max_dte` days, so the variants make no entries after 2024-11-01 (reference: after 2024-11-16).
  - The spread model has a separate 30-60 DTE bucket, so longer-dated fills are priced with their own fit.
  - A 21-DTE time exit binds only on trades held about 3 weeks; trades closed earlier by the flat exit or a stop are affected only through the contract they hold.
- **Runs:** each variant at 1x and 2x spreads. Costs are $0.65 per contract and $0.005 per share, with a $1 minimum per order. That makes 4 trials, plus the 2 reference trials reused from 2026-10-16-short-only (not rerun). The baseline is not stale.

## Metric and pass bar
Primary `dte45` against reference `short_only` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. Longer-dated shorts carry more vega, so a vol spike could deepen daily losses even with less gamma.

**Event floor:** `dte45` must have at least 30 round trips at 1x (the reference has 100). Otherwise there are too few trades to judge and the result is INCONCLUSIVE. The floor counts round trips, not time exits, because the change applies to every trade: each one holds a longer-dated contract and is measured on a longer-dated signal. A time-exit count would measure how often trades survive the flat exit, not whether the window changed. `experiment.py` counts round trips for the floor (`event = "round_trips"`).

**Hold-out bar** (only if it passes, and only when the PM asks): `dte45` against the hold-out baseline (live rules) over 2025-01-01 to 2026-07-10, at 1x and 2x. Net P&L must be higher, and |ES 5%| no more than 1.10 x the baseline's.

## If it passes
Combine it with the other passing rules (short-only, hedge band) into one candidate. Run the hold-out once on that combination, then shadow mode, then a decision record, then the change to `[entry]` and `[exit]` in `configs/paper.toml`.

## Changes
