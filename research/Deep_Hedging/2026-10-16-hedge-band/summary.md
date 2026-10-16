# Summary: 2026-10-16-hedge-band

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** passed (in-sample; the hold-out run is still to do)

Full report: [2026-10-16-hedge-band.pdf](2026-10-16-hedge-band.pdf)

## Result
Re-hedging only when the drift reaches 10 shares (`band10`) beat re-hedging every share on every check, at both 1x and 2x spreads. Development window 2014-06-02 to 2024-12-31; compared with baseline trial 1.

| Pass bar | 1x: band10 vs baseline | 2x: band10 vs baseline | |
|---|---|---|---|
| Net P&L, full window | −$1,096.9 vs −$2,059.5 | −$3,258.5 vs −$4,122.3 | pass |
| Net P&L, 2014-06 to 2019-12 | −$779.7 vs −$986.2 | −$1,408.5 vs −$1,511.3 | pass |
| Net P&L, 2020-01 to 2024-12 | −$317.2 vs −$1,073.3 | −$1,850.0 vs −$2,610.9 | pass |
| abs(ES 5%) ≤ 1.10 × baseline | 98.1 vs 96.5 (1.02×) | 106.8 vs 104.5 (1.02×) | pass |

Other numbers: hedge orders went from 914 to 469 (hedge fees from $914 to $469), Sharpe from −0.36 to −0.19 at 1x, and max drawdown from $3,027 to $2,505 at 1x. The book still loses money.

Where the $963 gain at 1x comes from: $445 in hedge fees saved, $717 in better share-leg P&L on the 130 round trips that are the same in both runs, and −$200 from one short that now hit a stop (2015).

Sensitivity only (cannot change the verdict): `band5` −$1,665.5 / −$3,725.4 (1x / 2x), ES about the same as the baseline. `band20` −$2,224.1 / −$4,394.7, ES about 1.2× the baseline, so it would have failed both bars.

## Trials
6 trials for this experiment (3 variants × 1x and 2x, one run each) plus the baseline's 2, so 8 in total. The run's report step crashed on a registry read while the parallel experiments were writing. All 6 trials were already registered, and the charts were rebuilt with `--report-only`, which adds no trials. After the run, a P&L split (bridge chart) was added to the report code. The pass bar was not changed.

## What surprised you
- **The band changed hedging P&L, not only fees.** The share-leg gain ($717) was larger than the fee saving ($445). But it is not steady across bands: $138 at band5, $717 at band10, $13 at band20, where longs gained $1,117 and shorts lost $1,104. It looks like path noise that happened to favour 10 shares.
- **Stops fired for the first time.** The baseline never hit a stop in ten years. With a band, a short's option-plus-hedge P&L drifts further before re-hedging: band10 hit one stop and band20 two. The flattening hedge after the band10 stop filled about $4 a share away from the decision snapshot.
- **Leftover shares while flat didn't matter.** At band10 no close left fewer than 10 shares, so the book was never flat with shares on. Only band20 had some, on 6 flat days, and they made $180.
- **P&L peaks at 10 shares** in both halves and at both multiples, and band20 is worse than the baseline.

## Caveats
- The idea came from the baseline's fee total on the same window, so this is in-sample evidence. Promotion needs one hold-out run.
- The pre-chosen band sits at the peak of the three tried. Part of its lead is likely luck (see the share-leg point above). Only the fee saving is mechanical.
- With one contract the $1 minimum is large relative to size. With more contracts each hedge order is bigger, so the $1 minimum matters less and the fee saving per contract shrinks.
- The spread model was fitted on about two weeks of calm 2026 live quotes. Month-end R2 days are missing (3.3% of scheduled times skipped).
- Hedges run once a day at 10:15 ET. Stops use option-plus-hedge P&L, so the band changes when stops fire, and the stop effects rest on 1 to 2 events.

## Next step
Run `band10` once on the hold-out (2025-01-01 to 2026-07-10) with the same pass bar. Expect the fee saving to carry over and the share-leg gain to be smaller, or of either sign. If it holds, run `min_shares = 10` in shadow mode next to the live hedge, then the PM decides on the one-line `[hedge] min_shares = 10` change in `configs/paper.toml`, with a decision record.
