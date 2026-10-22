# Summary: 2026-10-21-signal-times

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-21 · **Verdict:** passed (entries-only bar; net P&L worse)

Full report: [2026-10-21-signal-times.pdf](2026-10-21-signal-times.pdf)

## Result
Running the daily loop (signal, exits, entry, hedge) every hour from 10:15 to 15:15 ET (`hourly`) makes more entries than one run at 10:15. It meets the PM's entries-only bar at 1x and 2x. Development window 2014-06-02 to 2024-12-31; current paper rules; only `[schedule]` changed.

| Check (`hourly` vs baseline) | 1x | 2x | |
|---|---|---|---|
| Round trips, full window | 225 vs 131 | 225 vs 131 | pass |
| Round trips, 2014-06 to 2019-12 | 92 vs 44 | 92 vs 44 | pass |
| Round trips, 2020-01 to 2024-12 | 133 vs 87 | 133 vs 87 | pass |
| abs ES 5% ≤ 1.10 × baseline | 85.6 (limit 106.1) | 94.3 (limit 115.0) | pass |

Net P&L, not part of the bar, is worse: −$3,848 against −$2,060 at 1x and −$6,705 against −$4,122 at 2x. Hedge orders rise from 914 to 4,453 ($1 minimum each).

**One run a day at another time** (secondary, same checks): 12:45 gives 135 round trips (ties the baseline in 2020-2024, fails) and −$2,746 at 1x. 15:45 gives 144 round trips but a worse tail (ES 110.8 against a limit of 106.1, fails) and −$3,504 at 1x. Moving the single run barely changes entries: the signal is long or short on about 22% of runs at every time of day.

## Trials
6 trials (3 variants × 1x and 2x, one run at commit 2784f7c) plus the baseline's 2. Registry: 70 rows. None of this experiment's trials are tagged `-dirty`. The pass bar was set with the PM before the run and was not changed.

## What surprised you
- **Most extra entries are churn from the flat exit.** 71 of the 94 extra round trips open and close on the same day, all on the flat exit, all after two flat days. The 3-day flat rule counts the last signal of each previous day plus the current run. So after two flat days, one flat reading an hour after entry closes the position. These 71 are about flat net (+$44 at 1x, −$510 at 2x).
- **Before commissions, hourly is better.** Round trips earn +$1,581 against −$986 at 1x. The $1 minimum on 4,453 mostly tiny hedge orders (median 2 shares) costs $3,539 more and turns that into a loss. On 53 matched trades with the same entry and exit days, hourly earned +$902 against +$50 before commissions. That comes from hedging and exiting at different times of day, on a small sample, and may be noise.
- **Entries after 10:15 lose money even before commissions** (104 entries, −$680 at 1x).

## Caveats
- In-sample idea; the bar measures counts, which rise almost mechanically with more runs.
- One contract: the $1 order minimum dominates hedge costs.
- Six hedges a day lean six times as much on the parity-implied intraday spot.
- The spread model was fitted on two weeks of calm 2026 quotes; 3.6% of hourly times were skipped, mostly month-end days missing from R2.
- Round-trip sums differ from daily-equity P&L by $715 for `hourly` and $314 for `midday` at 1x (baseline within $21), so round-trip figures are attributions; headline numbers use daily equity.

## Next step
Don't promote: more entries cost money here. A hold-out run would mostly confirm a mechanical count. Possible follow-ups, each with its own card: hourly signal with a once-a-day hedge or the 10-share hedge band; and, as a PM decision first, a flat exit that counts the entry's own signal so intraday entries aren't closed an hour later.
