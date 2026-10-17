# Summary: 2026-10-16-dte-45-21

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed

Full report: [2026-10-16-dte-45-21.pdf](2026-10-16-dte-45-21.pdf)

## Result
On the short-only book, entering near 45 DTE (min 35, max 60) and exiting at 21 DTE did not beat the live 30-DTE entry and 7-DTE exit on the pre-registered bar. It lost a little at 1x, gained a little at 2x, was better in 2014-2019 and worse in 2020-2024 at both spreads. Development window 2014-06-02 to 2024-12-31.

| Check (`dte45` vs `short_only`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | −$886 vs −$774 | −$2,156 vs −$2,351 | fail 1x, pass 2x |
| Net P&L, 2014-06 to 2019-12 | −$559 vs −$875 | −$949 vs −$1,261 | pass |
| Net P&L, 2020-01 to 2024-12 | −$327 vs +$101 | −$1,207 vs −$1,090 | fail |
| abs ES 5% ≤ 1.10 × reference | 81.0 (limit 94.1) | 85.4 (limit 101.7) | pass |
| Round trips (event floor ≥ 30) | 95 | | met |

`dte45_exit14` (sensitivity, 14-DTE exit) did better: −$575 at 1x and −$1,756 at 2x. It still failed the 2020-2024 half at 1x (−$22 vs +$101).

## Trials
4 trials (2 variants × 1x and 2x, one run); baseline trial 1 (2 earlier trials) is shown for context. The reference was reused from `2026-10-16-short-only/short_only` (2 trials, not rerun). The pass bar was not changed.

## What surprised you
- **The exit barely moved.** The 3-day flat exit still closes 82 of 95 trades after about a week, so the median exit moved from 22 DTE to 35 DTE. Only 13 trades reached the 21-DTE exit.
- **Cheaper to trade, but less P&L before costs.** Trading costs fell $373 at 1x (spreads −$307, commissions −$66), and about $680 at 2x. Before costs, the book earned about $485 less (+$1,288 vs +$1,774). The two roughly cancel.
- **The round-trip gross is misleading here.** Round-trip P&L before commissions rose by $500 at 1x, but equity P&L fell by $112. The difference is the unattributed unwind residual (−$799 against −$122 for the reference). Most of it is the hedge-unwind fill gap: the option closes at the fill price but the hedge is marked at the decision spot (−$765 against −$71). That gap is noise, with a standard deviation of roughly $750-800 over a run, larger than the margins in this test.
- **The signal hardly changed.** VRP measured on the 43-DTE expiry agrees with the 30-DTE one on 96% of days. 59 of 95 trades started on the same day as a reference trade.
- **One year decides the second half.** 2020 alone is −$720 at 1x, from trades entered on different days around the crash and in June. 2022 is +$661. Without 2020 the second half would have been ahead at both spreads (a counterfactual, not part of the bar).

## Caveats
- In-sample: the idea comes from the 2026-10-16 desk discussion of the baseline on this window.
- One contract: the $1 order minimum makes hedge orders most of the commissions.
- The spread model has separate fits by DTE, fitted on two weeks of calm 2026 quotes. Part of the cost saving comes from those fits.
- The chain lists expiries up to 60 DTE and drops thin ones, so the rule picked a median 43 DTE, not 45. Month-end R2 days are missing (89 skipped times).

## Next step
Keep the live 30-DTE entry and 7-DTE exit. The 45/21 window is roughly neutral on this book. A follow-up needs its own card and is in-sample: 45-DTE entries with a 14-DTE exit, on the short-only book with the 10-share hedge band.
