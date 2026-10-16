# Summary: 2026-10-16-stop-cooloff

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** inconclusive (too few events)

## Result
The card's event floor was not met. With the tighter stops (short 0.5x credit, long 25% of premium), the reference `cool1` had only 3 stop exits at 1x over 2014-06-02 to 2024-12-31, below the minimum of 5. So the verdict is INCONCLUSIVE and the live 1-day cool-off stays.

For information only (not counted). `cool5` and `reset` gave identical trades.

| | `cool1` (live rule) | `cool5` / `reset` | Would beat? |
|---|---|---|---|
| Net P&L, full window, 1x / 2x | -$2,331 / -$4,540 | -$2,120 / -$4,289 | yes |
| Net P&L, 2014-06..2019-12, 1x / 2x | -$1,083 / -$1,715 | -$1,083 / -$1,715 | no (tie) |
| Net P&L, 2020-01..2024-12, 1x / 2x | -$1,247 / -$2,825 | -$1,037 / -$2,574 | yes |
| ES 5% (daily), full window, 1x / 2x | -98.1 / -107.1 | -93.9 / -102.8 | yes |

Even without the floor, the first-half tie would have failed the bar. `cool0` (no cool-off): -$2,351 / -$4,584, ES -100.7 / -110.0. Baseline (live stops, never fired): -$2,060 / -$4,122, ES -96.5 / -104.5.

## Trials
8 trials in this experiment (4 variants x 1x and 2x), run once with the card committed beforehand (8d1f0fe); 10 including the baseline's 2. `cool1` has the same configuration as `2026-10-16-stop-levels/tight` and reproduces it exactly. It is a duplicate trial, accepted by the PM.

## What surprised you
- The tighter stops fired only 3 times in ten and a half years (August 2015 short, February 2020 short, March 2020 long). All the differences come from the two stops in 2020.
- The gain from waiting was not from avoiding losing re-entries. The 1-day rule's two same-side re-entries lost only $47 in total, and the four immediate re-entries with no cool-off made $169. Most of the $210 difference is path dependence: skipping a re-entry changed which trades came next in the 2020 rebound.
- On this data, a 5-day wait and waiting for a signal reset block exactly the same days.

## Caveats
- The idea came from the baseline on the same window, so this is in-sample. A pass would still have needed a hold-out run.
- Only 3 stops, 2 of them in one crash.
- The result depends on tighter stops than the live ones. The live stops never fired, so the cool-off has had no effect on the live configuration.
- One contract, so the $1 order minimum dominates hedge costs (the same in every variant).
- The spread model is fitted on about two weeks of calm 2026 quotes, so it is probably too narrow in crashes, which is when stops fire.
- 3.3% of scheduled times were skipped (missing month-end R2 days).

## Next step
Archive as inconclusive and keep `stop_cooloff_days = 1`. A retest needs more stop events, for example the same rule on QQQ/IWM options or a stop level that fires more often, with a new card.

Report: [2026-10-16-stop-cooloff.pdf](2026-10-16-stop-cooloff.pdf)
