# Hypothesis: sizing the always-on 25-delta put to a 35% stress budget beats one contract at both spreads

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-22-stress-sized-puts` (config: `configs/experiments/2026-10-22-stress-sized-puts.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-22 |

## Hypothesis
The always-on 25-delta short put with the daily 10-share hedge (`always25`), sized at every entry to the most contracts whose loss in a one-day 20% SPY drop with implied vol at 60% stays within 35% of capital ($87,500), earns more net P&L than one-contract `always25` at 1x and 2x spreads, over the full window and in each half, with a maximum drawdown within that $87,500.

## Why it matters for the desk
`always25` is the first desk book that is positive at both spreads, but at one contract it earns about $125 a year, and $1 order minimums take about a third of its gross. The 2026-10-22 deep-research report (`research/Misc_Research_Notes/2026-10-22-turning-the-backtest-positive.pdf`) recommended sizing to a stress-loss budget instead of tighter stops. The PM set the budget at 35% of capital for a one-day 20% crash and asked to compare hedged, banded and unhedged books. If the sized book passes, it is the desk's first candidate for live trading at a size that matters.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the book is `always25` (`Agentic_Routing/2026-10-17-always-short`), whose 2014-2024 result motivated this test. The stress scenario and the Whalley-Wilmott band come from the 2026-10-22 deep-research report, which was written with the desk's registered results in view. The PM set the 35% budget after reading that report, which showed only one-contract results. No sized run exists yet.

## Method
- **Book (all variants):** the always-on short 25-delta put of `always25`.
  - The signal is ignored (`short_band = long_band = -inf`) and the flat exit is off (`flat_days = 999`). The book rolls at the 7-DTE time exit.
  - The 1x-credit stop, the 50% profit-take, the 1-day cool-off after a stop and the embargo before the hold-out stay as live. One position at a time; decisions and hedges once a day at 10:15 ET.
- **Sizing** (new research switch `[backtest] stress_budget`, off by default). At each entry, contracts = the largest n with

  n × (put loss in the scenario − hedge gain) + (shares left unhedged inside the band) × 20% × spot ≤ 35% × $250k.
  - **Scenario:** spot falls 20% at once. IV goes to max(60%, the put's IV), with the same expiry. Black-Scholes, r = 0, no early exercise.
  - **Hedge gain:** |delta| × 100 shares per contract × 20% × spot. The unhedged variant gets none. The banded variant loses its band width; the 10-share hedge loses 10 shares.
  - **Inputs:** read from the decide-time chain (15-minute-old data), like every other decision. Short puts only; a long call would keep `[size] quantity`.
  - **Today:** on the 2026-10-21 chain (spot $769, 25-delta Nov-20 put), this gives 8 contracts hedged, 7 banded and 6 unhedged (desk calculation, not a backtest result). One contract loses about $13,500 unhedged and $9,700 hedged in the scenario.
- **Variants:**
  - `hedged` (primary): the daily hedge with the 10-share band, as in `always25`.
  - `banded` (sensitivity): a Whalley-Wilmott band (new research switch `[backtest] ww_band`). It re-hedges fully to delta once the drift reaches max(1, 30 × √(book gamma in shares per $1)) shares. The constant 30 is the fixed-cost formula (12 k1 / g)^(1/4) with k1 = $1 and risk aversion g of about 3.7 / $250k, in the middle of the report's range. Today that is about 80 shares at 8 contracts, against a position delta of about 200 shares.
  - `unhedged` (sensitivity): `min_shares = 1e9`, never hedges.
- **Reference:** the registered `2026-10-17-always-short/always25` runs (+$1,315.51 at 1x, +$862.29 at 2x), reused, not rerun. Its config equals `hedged` except for the stress budget. Baseline trial 1 is shown for context.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); 6 trials. The baseline is current (the new switches are off by default and reproduce baseline trial 1), so no fresh baseline is needed.
- **Also reported, not part of the bar:**
  - contracts per entry by year, Sharpe, ES 5% and the worst day for each variant;
  - **Tiered vs Fixed:** every hedge order of every run re-priced under IBKR Pro Tiered ($0.0035 per share, $0.35 minimum, plus about $0.0032 per share of exchange and clearing fees for market orders). Option orders cost the same under both plans: IBKR Pro has one US-option schedule, with OCC, ORF and CAT fees on top in both (not modelled). Fees never change a decision, so this needs no new runs. Tiered is recommended if it cuts the primary's hedge commissions on its 2023-2024 orders, the SPY level closest to today's;
  - **equity beta for `unhedged`:** the P&L of holding the book's option delta in SPY between decisions, and the rest.
- **Not modelled:** margin. On the 2026-10-21 chain, Reg-T needs about $13,800 per put, about $110k for 8 puts plus about $76k for their short-share hedge, or $83k for 6 unhedged puts (desk calculation).

## Metric and pass bar
Primary `hedged` against reference `always25` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. Net P&L is above zero over the full window. This is absolute; it binds on the hold-out, where the reference is the hold-out baseline;
5. The maximum drawdown is at most $87,500 (35% of $250k): the realised path must not lose more than the one-day stress budget. This replaces the usual 1.10x ES guard, because size is the target here and ES grows with contracts by design.

**Event floor:** `hedged` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `hedged` over 2025-01-01 to 2026-07-10, at 1x and 2x: net P&L higher than the hold-out baseline, net P&L above zero, and maximum drawdown at most $87,500.

## If it passes
Run the hold-out once. If it holds: shadow mode, a decision record, then live changes, each reviewed by the PM. Live needs:
- a 25-delta strike in `trading/selection.py`;
- the stress-budget size at entry in the runner;
- `short_band = long_band = -inf`, `flat_days = 999` and `min_shares = 10` in `configs/paper.toml`.

Tiered pricing, if chosen, is an IBKR account setting. `configs/backtest.toml` would then move to the Tiered share price in a separate commit, with a fresh baseline.

## Changes
- 2026-10-22 (before the run): the PM confirmed `hedged` as the primary, the pass bar and the hold-out bar above, and asked for 15% and 25% budgets as a follow-up card on the winning mode.
