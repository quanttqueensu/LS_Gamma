# Hypothesis: always being short a 25-delta put beats signal-timed shorts

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-17-always-short` (config: `configs/experiments/2026-10-17-always-short.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-17 |

## Hypothesis
On the 25-delta short-put book with the 10-share hedge band, being short every day regardless of the VRP signal (`short_band = -inf`, rolling each put at the 7-DTE time exit) raises net P&L over the signal-timed book at 1x and 2x spreads, over the full window and in each half, without a worse daily tail.

## Why it matters for the desk
The VRP signal is short on only about 18% of days, while implied vol ended above realized vol on about 70% of days in 2014-2024. The GARCH forecast runs 2-4 vol points high in calm years, so the signal sits out the years that are best for short vol (2017: no trades, true premium about +2 vol points). In the archived v1 backtest (2015-06 to 2021-12), the profitable agents were always short and ignored the signal, and the signal-timed strategy lost money. If always-short wins here too, the signal is the problem and the desk should harvest the unconditional premium with risk controls.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the desk's 2026-10-17 review of the baseline signal and from the archived v1 results, which cover 2015-2021 (inside this window). It was also partly tested on an IV-minus-realized proxy in `RV_Forecasting/2026-10-07-garch-bias-correction`, which shorted 3x as many days. Precision fell to the base rate, and losers grew in 2018 and 2022. This is the first test on option P&L.

## Method
- **Book:** the 25-delta short put (`[backtest] put_delta = 0.25`) with the 10-share hedge band, short-only, as in `2026-10-17-otm-put/put25`. Exits and hedges run once a day at 10:15 ET.
- **What changes:** `[signal] short_band = -inf`, so the signal is always short. After every exit the engine re-enters on the same run, so the book rolls continuously. The flat exit cannot fire; `flat_days = 999` makes that explicit.
- **What does not change:**
  - The 7-DTE time exit, the 1x-credit stop, the 50% profit-take, the 1-day cool-off after a stop, and the embargo before the hold-out.
  - The archived v1 held to 3 DTE with no stops; that is not tested here.
- **Variants:** `always25` (primary), and `always_atm` (sensitivity, reported only: the same rules with the ATM put, closest to the archive's single-leg analogue).
- **Reference:** the registered `2026-10-17-otm-put/put25` runs (+$180.04 at 1x, −$272.64 at 2x), reused, not rerun. Its strategy config equals the primary's except `short_band = 0.02` and `flat_days = 3`. Baseline trial 1 is shown for context.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order; 4 trials.
- **Also reported, not part of the bar:**
  - P&L in four windows: 2014-06 to 2015-05, 2015-06 to 2021-12 (the archive's window), 2022, and 2023-2024. This shows how much of any result depends on 2022.
  - Share of days holding a position, and exits by reason.

## Metric and pass bar
Primary `always25` against reference `put25` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. Always-short holds a position far more often, so the daily tail is the main risk; the guard is kept at the desk's standard 1.10.

**Event floor:** `always25` must have at least 30 round trips at 1x; otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `always25` against the hold-out baseline over 2025-01-01 to 2026-07-10, at 1x and 2x: net P&L higher and |ES 5%| within 1.10x.

## If it passes
Run the hold-out once. If it holds: shadow mode, a decision record, then live changes. `short_band` is a `configs/paper.toml` value, but the 25-delta strike needs a change to live strike selection (`trading/selection.py`), reviewed by the PM.

## Changes
- (dated notes, if the plan had to change)
