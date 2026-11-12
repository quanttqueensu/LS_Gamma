# Summary: 2026-11-11-trend-long-band

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-11 · **Verdict:** failed

Full report: [2026-11-11-trend-long-band.pdf](2026-11-11-trend-long-band.pdf)

## Result
The test widened the share-hedge band on long calls to 30 shares when SPY was trending: a 10-day efficiency ratio of at least 0.4, from completed closes. Otherwise the book re-hedged every share as the paper rules do. It failed: net P&L was lower than the baseline over the full window and in both halves, at 1x and 2x.

The primary is `trend30`, the comparison is the baseline (current paper rules), and the window is 2014-06-02 to 2024-12-31.

| Check (`trend30` vs baseline) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | −$2,177 vs −$2,060 | −$4,239 vs −$4,122 | fail |
| Net P&L, 2014-06 to 2019-12 | −$989 vs −$986 | −$1,514 vs −$1,511 | fail |
| Net P&L, 2020-01 to 2024-12 | −$1,188 vs −$1,073 | −$2,725 vs −$2,611 | fail |
| ES 5% within 1.10x | −$100.6 vs −$96.5 | −$108.5 vs −$104.5 | pass |
| Hedges held back (floor ≥ 30) | 37 | | met |

Sensitivities (reported only, 1x):
- `always30` (the same band on every long-call day, no detector): −$1,881, $179 better than the baseline.
- `trend15` (15-share band in a trend): −$1,704, $356 better.

Neither is reliable: t = 0.21 and 1.34 on the changed round trips.

## Trials
6 trials (3 variants × 1x and 2x, one run of `experiment.py`) on the pre-registration commit a8ac9e0. There were also 2 fresh `baseline` trials: the registered baseline no longer matched the config after two live-only `paper.toml` order settings changed (option slippage and the share-order pad), and the fresh run reproduces the old one exactly. The registry now has 148 rows, none on the out-of-sample window. The pass bar was not changed.

## What surprised you
- **On the long side, hedging made money and the calls lost it.** Over the baseline's 30 long-call round trips, the share hedge made +$2,115 and the calls lost $3,822. Short SPY hedges cost money in November's rally on the paper account, but over 2014-2024 they paid on average.
- **Every book traded the same 131 positions.** No exit changed, so all differences come from hedges and their commissions. `trend30` saved $39 in hedge commissions and lost more than that on the hedges.
- **The detector didn't predict continuation.** Over the 47 holding intervals that started on a trending day with a long call held, `trend30` lost $262 against the baseline while `trend15` gained $250 on the same intervals: opposite signs at two band widths.

## Caveats
- In-sample: the idea came from the live book and the 2026-10-16 short-only result on this window; the 0.4 threshold came from the feature distribution here (no P&L by regime was looked at).
- Small sample: 30 long-call round trips and 37 held hedges for the primary. Effects of $100-$350 over ten years are within noise.
- One contract: the $1 minimum per order makes each saved hedge worth $1.
- The spread model was fitted on calm 2026 quotes (the 2x run is the stress test); about 3.3% of scheduled times are skipped.

## Next step
Archive this card. A hedge-band rule for long calls would need a detector that predicts next-day continuation, not past trend, and would be hard to judge on 30 round trips. The long side's loss is in the calls themselves. The 2026-10-16 short-only card (passed in-sample) already tests dropping them.
