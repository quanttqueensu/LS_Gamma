# Summary: 2026-10-16-short-only

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** passed (in-sample; the book still loses money)

## Result
All three pre-registered bars hold at 1x and 2x spreads. The comparison is baseline trial 1 on the development window, 2014-06-02 to 2024-12-31. Full report: [2026-10-16-short-only.pdf](2026-10-16-short-only.pdf).

| Bar | 1x short_only vs baseline | | 2x short_only vs baseline | |
|---|---|---|---|---|
| Net P&L, full window | −$774 vs −$2,060 | pass | −$2,351 vs −$4,122 | pass |
| Net P&L, 2014-06..2019-12 | −$875 vs −$986 | pass | −$1,261 vs −$1,511 | pass |
| Net P&L, 2020-01..2024-12 | +$101 vs −$1,073 | pass | −$1,090 vs −$2,611 | pass |
| abs ES 5% (daily) ≤ 1.10 × baseline | $85.5 (limit $106.1) | pass | $92.4 (limit $115.0) | pass |
| Max drawdown ≤ 1.10 × baseline | $2,220 (limit $3,330) | pass | $3,222 (limit $4,684) | pass |

Sharpe goes from −0.36 to −0.15 at 1x and from −0.68 to −0.43 at 2x. Round trips go from 131 to 100, and commissions fall by $206 ($970 vs $1,176). The short-only book is less bad, not profitable.

## Trials
There are 2 trials for this experiment (`short_only` at 1x and 2x, one run, commit 8d1f0fe) plus the baseline's 2, so 4 in this comparison. The script was run once. Its reporting step crashed after both trials were registered, because it read the registry while a parallel experiment was writing. The charts and tables were rebuilt with `--report-only`, which adds no trials. The pass bar was not changed.

## What surprised you
- **The single position slot did not matter.** All 100 short-only shorts opened on days the baseline also opened a short, so the books differ only by the missing long trades and by how shorts exit.
- **The long signal was working as a stop for shorts.** In the baseline, a long signal closes an open short at once ("flip"). Without it, 13 of those 14 shorts wait for three flat days and lose more (the 14th is never opened). The short side goes from −$148 to −$562 at 1x, mostly in the March 2020 sell-off. So the gain ($1,286 at 1x) is smaller than the long side's loss ($1,913).
- **The first-half margin is thin:** $111 at 1x and $250 at 2x. Most of the gain comes from 2022–2024, when the baseline's long trades lost most.
- Short-only's worst drawdown moves to the COVID crash (trough 2020-03-12 at 1x). It was the slow 2022–2024 bleed for the baseline.

## Caveats
- The idea came from the baseline's per-side split on this same window, so this is in-sample evidence. Only the hold-out can confirm it.
- One contract, so the $1 minimum per order dominates. Hedge commissions ($770) are larger than the short-only gross round-trip P&L at 1x (+$318).
- The spread model was fitted on about two weeks of calm 2026 live quotes. Month-end R2 days are missing (3.3% of scheduled times skipped).
- Few events: 38 short-only trades in the first half, and the second-half gain rests on three years.
- The per-side split uses round trips, which leave out the share unwind after each close. That residual is about −$212 (1x) for short-only versus +$1 for the baseline. The pass bar uses daily equity, which includes everything.

## Next step
Don't change `paper.toml` on this result. Per the card, the next step is one hold-out run of `short_only` (2025-01-01 to 2026-07-10), if the PM approves. A follow-up worth pre-registering is a book with no long entries that still closes a short on a long signal. It would keep the early exit that protected shorts in 2020. That idea also comes from this window, so it would need its own pass bar and the hold-out.
