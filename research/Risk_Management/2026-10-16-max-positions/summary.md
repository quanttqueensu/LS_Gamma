# Summary: 2026-10-16-max-positions

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed

Full report: [2026-10-16-max-positions.pdf](2026-10-16-max-positions.pdf)

## Result
The hypothesis was that net P&L peaks at an interior number of laddered same-side positions. It failed at both spreads and in both halves. Net P&L is highest at N = 1, the live setting. Development window 2014-06-02 to 2024-12-31. N = 1 is baseline trial 1.

| Check | 1x | 2x | Bar | |
|---|---|---|---|---|
| N with the highest full-window P&L | 1 | 1 | interior (2-6) | fail |
| Peak minus the better end | $0 | $0 | ≥ $500 | fail |
| Best N, 2014-2019 / 2020-2024 | 1 / 1 | 1 / 1 | interior | fail |
| Ladder entries at N = 8 (event floor) | 328 | | ≥ 30 | met |

| max_positions | 1 | 2 | 3 | 4 | 6 | 8 |
|---|---|---|---|---|---|---|
| Net P&L 1x | −2,060 | −4,586 | −6,433 | −6,118 | −6,836 | −5,807 |
| Net P&L 2x | −4,122 | −7,970 | −10,699 | −10,944 | −12,450 | −11,974 |
| ES 5% (daily) 1x | −96.5 | −177.2 | −243.4 | −291.5 | −370.9 | −426.3 |
| Peak est. Reg-T margin ($k) | 31 | 61 | 90 | 116 | 162 | 192 |

At 1x the curve falls from N = 1 to 3, stays flat to 6 and recovers a little at 8. At 2x it keeps falling to 6. The daily tail grows 4.4x by N = 8.

## Trials
10 trials (5 variants × 1x and 2x, one run of `experiment.py`) plus the baseline's 2. The engine change (research-only `[backtest] max_positions`, commit 25b6fc2) was first checked against baseline trial 1 by calling the engine directly. That check is unregistered, and it reproduced trial 1 exactly. The pass bar was not changed.

## What surprised you
- **Laddered shorts that came in late made money.** At N = 8 (1x), shorts opened as the third or later position made +$3,207 over 215 trades, mostly in 2020, 2021 and 2024. The short side as a whole was positive (+$813). At 2x it was negative (−$3,513).
- **The ladder pays at the flip.** When the signal turns long, every short closes at once: short flips lost −$6,959 at N = 8, against −$745 at N = 1. Time exits made +$9,052.
- **Longs lose at every rank** (about $57-63 each), so laddering long signals only adds a losing trade. This matches `2026-10-16-short-only`.
- **Round-trip figures leave out the unwind.** The side and rank totals above are round-trip P&L. They miss the order that flattens the hedge after the last close. At N = 8 (1x) that is −$1,585 of −$5,807, about $2.1k of it after long closes. The pass bar uses equity P&L.
- **Sharpe is not monotone** (−0.36, −0.44, −0.44, −0.35, −0.30, −0.21 at 1x). It gets less negative at large N because daily P&L volatility grows about 4.7x while the average loss grows about 2.8x. It is not a better book.
- Netting keeps hedge orders flat (914 to 941). Option commissions grow with round trips ($262 to $898).

## Caveats
- The window has been used by five earlier experiments, although the hypothesis itself is the PM's prior.
- The engine's modelling choices (agreed with the PM): one entry per 10:15 run, flip and flat close everything, and netted hedges split across positions. Staggered exits or a minimum gap between entries could change the shape.
- The margin is a simple Reg-T estimate, not IBKR's real calculation.
- One contract per position. The spread model was fitted on calm 2026 quotes. Month-end R2 days are missing (89 skipped times at every N).

## Next step
Keep one position (`max_positions` stays at the live 1). No hold-out run is needed. A possible follow-up with its own card: ladder short signals only. It's in-sample, and it looked good at 1x but not at 2x.
