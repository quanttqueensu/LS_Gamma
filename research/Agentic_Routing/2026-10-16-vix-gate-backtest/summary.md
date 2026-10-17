# Summary: 2026-10-16-vix-gate-backtest

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed

Full report: [2026-10-16-vix-gate-backtest.pdf](2026-10-16-vix-gate-backtest.pdf)

## Result
On the short-only book, skipping short entries when the prior close's VIX/VIX3M is ≥ 1 (`gate1`) cut the daily 5% tail by about 11-12% (11.6% at 1x, 11.1% at 2x), not the 20% the bar needed, and it lost net P&L at both spreads. Development window 2014-06-02 to 2024-12-31, compared with the registered `2026-10-16-short-only/short_only` runs.

| Check (`gate1` vs `short_only`) | 1x | 2x | |
|---|---|---|---|
| abs ES 5% ≤ 0.80 × reference, full window | 75.6 (limit 68.4) | 82.2 (limit 74.0) | fail |
| abs ES 5% smaller, 2014-06 to 2019-12 | 45.2 vs 45.7 | 49.2 vs 49.7 | pass |
| abs ES 5% smaller, 2020-01 to 2024-12 | 101.6 vs 120.2 | 109.8 vs 129.1 | pass |
| Net P&L at least the reference's | −$1,148 vs −$774 | −$2,568 vs −$2,351 | fail |
| Days the gate blocked a short (floor ≥ 10, 1x) | 21 | | met |

`gate095` (sensitivity) blocked 83 days and cut ES by about 18% at both spreads, still short of 20%. It lost more: −$1,736 at 1x and −$2,913 at 2x.

## Trials
4 trials (2 variants × 1x and 2x, one run, commit fc6e788). The reference reuses the 2 registered `short_only` trials, which were not rerun: with the gate off, the engine reproduces that run's equity exactly. After the run, one chart was fixed (marker overlap) and the figures were rebuilt with `--report-only`, adding no trials. The pass bar was not changed.

## What surprised you
- **The gate removes winners.** The reference's 9 shorts that entered on would-gate days made +$1,170 net at 1x on the round-trip ledger. Shorts opened just after the VIX curve inverts collect inflated premium as volatility falls back. 90 of the reference's 100 round trips are unchanged; the gate drops 10 and adds 2.
- **The tail cut is one week.** The reference's worst day (−$703 at 1x, 2020-03-12) sits inside a short opened on 2020-03-09 after a 1.18 close; `gate1` skips it. Zeroing that week alone takes the reference's ES from −85.5 to −78.1, about three quarters of the gate's cut. In 2014-2019 the ES gain is about 1%.
- **The fill-gap residual was not noise here.** The 1x bridge is −$1,173 round-trip P&L before commissions, +$58 commissions saved and +$741 unattributed unwind residual (equity minus round-trip gross net of all commissions), for −$374 (at 2x: −$1,016, +$58, +$742, for −$217). Most of the residual is one hedge unwind in March 2020 that filled about $440 worse in total than the decision spot. So the round-trip ledger overstates the gate's cost, but on equity it still loses money, mainly from skipping profitable post-spike shorts in April 2020 and August 2024.
- **The gate rarely gets a chance to fire.** The curve closed inverted on 193 days. A short was already open on 83 of them and the signal was flat on 82, which leaves 21 blocked days, 13 of them in 2020.

## Caveats
- In-sample: the idea comes from desk discussion of this window and from the 2026-10-07 proxy cards, whose data overlaps it.
- Few events: 21 blocked days and 10 changed trades, and the tail result rests on March 2020.
- The spot comes from put-call parity on a 30-minute grid, and fills use the next 15 minutes of trades, which is coarse in a crash. The spread model was fitted on calm 2026 quotes. One contract, with a $1 minimum per order. 89 month-end times are skipped.

## Next step
Archive the gate as an entry filter for the short-only book. A possible follow-up (its own card, in-sample on this window): gate only on the first day the curve inverts. The one loss avoided came at the start of a spike, while the gains given up came after it.
