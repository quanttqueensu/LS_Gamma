# Summary: 2026-10-16-har-signal

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed

Full report: [2026-10-16-har-signal.pdf](2026-10-16-har-signal.pdf)

## Result
On the short-only book, signalling with HAR instead of GARCH did not pass the pre-registered bar. It lost more money over the full window and in 2020-2024, at both spreads. The 2014-2019 half was a near-tie, and the tail guard held. Development window 2014-06-02 to 2024-12-31.

| Check (`har` vs `short_only`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | −$1,250 vs −$774 | −$2,682 vs −$2,351 | fail |
| Net P&L, 2014-06 to 2019-12 | −$854 vs −$875 | −$1,244 vs −$1,261 | pass |
| Net P&L, 2020-01 to 2024-12 | −$396 vs +$101 | −$1,438 vs −$1,090 | fail |
| abs ES 5% ≤ 1.10 × reference | 87.4 (limit 94.1) | 93.7 (limit 101.7) | pass |
| Round trips (event floor ≥ 30) | 86 | | met |

The P&L bridge from `short_only` to `har` is mostly round-trip P&L. The unwind residual is about −$200 in both books, so fill noise is not the story.

| Bridge item | 1x | 2x |
|---|---|---|
| Round-trip P&L before commissions | −$598 | −$456 |
| Commissions | +$108 | +$108 |
| Unwind residual | +$15 | +$17 |
| Change in net P&L | −$476 | −$331 |

## Trials
2 trials (`har` at 1x and 2x, one run, commit 671df4e), plus the baseline's 2. The reference was reused from `2026-10-16-short-only` (2 trials, not rerun). One chart (the forecast axis cap) was changed after the run and rebuilt with `--report-only`, which adds no trials. The pass bar was not changed.

## What surprised you
- **HAR mostly switched the book off.** Its forecast ran higher than GARCH's in calm years after 2020: the median daily gap was +2.2 points in 2021, +2.7 in 2023 and +3.4 in 2024. That cut short-signal days from 58 to 24 in 2021, 22 to 7 in 2023 and 24 to 1 in 2024. Those calm-year shorts were profitable for GARCH, and missing them cost $715 at 1x.
- **HAR broke down in March 2020.** Early in the month it lagged (median forecast 35 vs 40 for GARCH and 43 for IV). In the second half it swung between its variance floor (near 0%, on one day) and 777%. It signalled short on 3 late-March days when GARCH signalled none. Its two March shorts lost $1,046 together, and its 2020 was $744 worse.
- **2022 is the one year HAR helped** (−$470 vs −$1,433 at 1x). Its forecast was lower than GARCH's, and the gain came mostly from different exit timing on trades entered on the same days. It rests on a handful of trades.
- **Before 2020 the two forecasters barely differ:** 154 vs 157 short days, and P&L within about $20 in each half-window.

## Caveats
- In-sample: the idea comes from the 2026-10-16 desk discussion of the baseline on this window.
- This is the desk's HAR on squared daily returns, which has no positivity guarantee beyond a floor. It does not rule out a HAR built on Garman-Klass or intraday realized variance.
- With one position at a time, a changed entry shifts every later trade. The yearly gaps rest on few trades (86 round trips in total).
- One contract, the $1 order minimum, and a spread model fitted on calm 2026 quotes. 89 scheduled times (3.3%) are skipped for missing R2 month-end days.

## Next step
Archive this test and keep GARCH live. A possible follow-up, which needs its own card: HAR on Garman-Klass realized variance with a positivity guard, as suggested in `2026-10-05-har-vs-garch`.
