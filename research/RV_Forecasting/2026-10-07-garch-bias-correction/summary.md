# Summary: 2026-10-07-garch-bias-correction

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-10-07 · **Verdict:** failed

## Result
The correction removed the bias but made the signal no better, so it fails 2 of the 3 tests. Run on 2,220 daily forecasts (Oct 2016 to Aug 2025), IV = 0.83 × VIX:

| | Live GARCH | Corrected | Pass bar | |
|---|---|---|---|---|
| Median bias (forecast − realized) | +3.1 pts | +0.2 pts | under 1 pt | pass |
| Short days / precision | 349 / 73.1% | 1,025 / 69.4% | ≥ 78.1% | **fail** |
| Long days / precision | 151 / 34.4% | 69 / 44.9% | > 50% | **fail** |
| Flat share | 77% | 51% | | |
| QLIKE | 0.507 | 0.812 | (diagnostic) | |

Short precision actually fell. Long precision improved but is still below a coin flip. We keep live GARCH.

## Trials
One run (trial 1). The code was first checked on a coarse setting (every 20th day) without logging a run; that check is not counted as a trial. The pass bar was not changed.

## What surprised you
- **The bias wasn't the real problem.** Across all days, IV ended above realized vol 68.4% of the time. Short precision for both forecasts sits close to that base rate (73% live, 69% corrected). The band picks short days only slightly better than chance, whichever forecast feeds it.
- **The correction triples the number of short days** (349 to 1,025) by lowering the forecast. The extra days are ordinary ones, so precision drifts down toward the base rate.
- **It lags at turning points.** After a calm year, the trailing bias is large, so the forecast is cut just before vol spikes. In 2018 the corrected forecast ran 4 points *below* realized, and short precision was 54%. In 2022 it was 42%. QLIKE, which punishes under-forecasting, got worse for the same reason.
- **The losers got bigger.** On losing short days, realized vol beat IV by a median 5.1 points with the correction, against 3.8 for live. Winners shrank from 5.4 to 3.9 points.
- In calm years (2017, 2021, 2023) the corrected short days won 82–91% of the time. But in calm years almost any short wins.

## Caveats
- IV is approximated as 0.83 × VIX, not historical ATM IV. At 1.0 × VIX the conclusion is the same: short precision is 81.6% live vs 80.8% corrected, and long precision is 14% vs 4%.
- Precision is not P&L. It ignores the price path, hedging, costs and stops. A short that loses on vol can lose much more than a winner earns.
- The 0.83 ratio comes from 2026 snapshots, which fall inside the hold-out period (one number, not tuned).
- Overlapping 21-day windows mean the 2,220 forecasts are far from 2,220 independent tests.

## Next step
Archive. Don't promote the correction and don't tune the bands on this forecast.

The losing 30% of short days are the vol spikes, so the follow-up should be a **filter that skips shorts in stress**, not a better point forecast. That was the "VIX term gate" in the v0 signal plan. Suggested card: *skipping short signals when VIX/VIX3M ≥ 1 (inverted term structure) raises short precision by at least 5 points without cutting short days by more than half.* Long gamma likely needs a shock or regime trigger instead of a VRP threshold.
