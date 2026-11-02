# Summary: 2026-11-02-partial-hedge

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-partial-hedge.pdf](2026-11-02-partial-hedge.pdf)

## Result
On the 35% stress-sized `hedged` put book, hedging only half the delta of puts entered above 2 VRP points (`half2`), while keeping the book's full size, made more money than always hedging in every period. It still failed the bar at both spreads: Sharpe was lower and the drawdown broke the $87,500 stress budget. Development window 2014-06-02 to 2024-12-31; reference: the registered 2026-10-22 `hedged` runs.

| Check (`half2` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $142,653 vs $121,482 | $117,002 vs $101,172 | pass |
| Net P&L, 2014-06 to 2019-12 | $64,611 vs $49,132 | $54,135 vs $42,687 | pass |
| Net P&L, 2020-01 to 2024-12 | $78,041 vs $72,350 | $62,868 vs $58,485 | pass |
| Sharpe ratio | 0.50 vs 0.52 | 0.41 vs 0.43 | fail |
| Max drawdown ≤ $87,500 | $98,210 | $105,611 | fail |
| Partly hedged round trips (floor ≥ 20) | 38 | | met |

**Sensitivities** (reported only; they cannot pass this card). Both cleared every check at both spreads:
- **`none2`** (no hedge above 2 points, full size): net P&L $168,561 and $144,576; Sharpe 0.64 and 0.53; drawdown $84,054 and $86,055.
- **`half1`** (half hedge above 1 point): net P&L $188,041 and $168,355; Sharpe 0.65 and 0.57; drawdown $74,528 and $75,840.

## Trials
6 trials (3 variants × 1x and 2x, one run of `experiment.py`), plus the baseline's 2. The reference `hedged` and the context book `2026-11-02-vrp-hedge/vrp2` were reused, not rerun.

All six rows are tagged `3568520-dirty`. Other experiments of the same batch had uncommitted files in the shared working tree, and the tag names the batch's latest pre-registration commit, which includes this card's 79b09a1. The engine, config and script were unchanged.

The registry holds 134 trials. The pass bar was not changed.

## What surprised you
- **One put decides the verdict.**
  - On 2 March 2020, `half2` entered a 41-contract put at VRP 3.4 points with half its delta unhedged. The hedged book held the same put fully hedged.
  - Both were stopped on 12 March: `half2` lost $55.3k, the hedged book $29.8k.
  - That $25.5k is most of the drawdown gap ($98.2k against $70.4k at 1x) and more than the whole 2020 shortfall (−$21.8k).
- **The timing still shows up in the delta leg.**
  - The delta of partly hedged puts earned 30% a year per dollar held, against 7% for fully hedged puts.
  - Partly hedged puts made $52.6 per contract pooled, against $21.5.
  - Without the 2 March put, the other 37 partly hedged round trips made $108.3k, and 32 were profitable.
- **Partly hedged puts hit the profit-take far more often:** 22 of 38, against 21 of 157 fully hedged.
- **Outside 19 February to 30 April 2020, the half hedge clearly wins:** $144.9k against $99.8k at 1x, Sharpe 0.93 against 0.81.
- **The variants' ranking is mostly path.** `none2` was stopped on 9 March and re-entered on 10 March. It took a different route through the crash and ended with a smaller drawdown than `half2`. Only 137 of `half2`'s 195 round trips and 117 of `none2`'s 208 open at the same time as one of the hedged book's.

## Caveats
- **In-sample:** the idea came from the 2026-11-02 `vrp-hedge` results, including its `vrp1` sensitivity, which Claude saw before writing this card.
- **One episode:** March 2020 decides both the primary's failure and the sensitivities' passes.
- **Stress size:** a partly hedged put is sized as if fully hedged, so the 35% budget does not hold for it. This was the PM's choice for the card.
- **Model limits:** spread model fitted on calm 2026 quotes; margin not modelled; about 3.3% of scheduled times skipped.
- **Delta split:** an attribution (snapshot delta × spot change between 10:15 decisions), not a hedged return.

## Next step
Archive `half2` and run no hold-out. `none2` and `half1` are not promotable from this card. VRP timing of the delta now has support from two cards; the risk control is what failed. A follow-up needs its own card, for example:
- size partly hedged puts to the open delta in the stress test;
- or combine the half hedge with the crash-vol fix from `2026-11-02-crash-shock`.
