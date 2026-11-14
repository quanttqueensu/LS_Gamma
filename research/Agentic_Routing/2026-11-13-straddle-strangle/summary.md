# Summary: 2026-11-13-straddle-strangle

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-13 · **Verdict:** failed

Full report: [2026-11-13-straddle-strangle.pdf](2026-11-13-straddle-strangle.pdf)

## Result
On the VRP-band rules, the test traded an ATM straddle on long signals and a 20-delta strangle on short signals, 1 contract per leg. Each structure exits as one position (1 of 102 strangles split; see Caveats). It failed: daily net P&L became more volatile, not less, in every period and at both spread levels, and the drawdown and tail got worse. Only the net P&L floor held. The book lost less money (−$318 against −$2,060 at 1x).

The primary is `both`, compared with the baseline (the VRP-band rules, single ATM call or put), over 2014-06-02 to 2024-12-31.

| Check (`both` vs baseline) | 1x | 2x | |
|---|---|---|---|
| Daily P&L std, full window | $54.37 vs $35.64 | $54.75 vs $37.28 | fail |
| Daily P&L std, 2014-06 to 2019-12 | $25.80 vs $16.31 | $26.51 vs $17.84 | fail |
| Daily P&L std, 2020-01 to 2024-12 | $74.30 vs $48.94 | $74.61 vs $50.88 | fail |
| Max drawdown | $3,848 vs $3,027 | $4,405 vs $4,258 | fail |
| ES 5% within 1.10x | −$137.8 vs −$96.5 | −$142.3 vs −$104.6 | fail |
| Net P&L ≥ baseline − $1,000 | −$318 vs −$2,060 | −$1,855 vs −$4,122 | pass |
| Structures (floor 20 each) | 30 straddles, 102 strangles | | met |

Reported only (1x / 2x):
- `straddle_only`: −$3,783 / −$6,294.
- `strangle_only`: +$1,398 / +$302, the only positive book. Its daily std is $43.54 and its drawdown $2,435.

## Trials
6 trials (3 variants × 1x and 2x, one run of `experiment.py`) on the pre-registration commit 7d70155. The baseline was reused (the 2026-11-11 pair, which matches the current config), with no fresh run. The registry now has 154 rows, none on the out-of-sample window. The pass bar was not changed.

## What surprised you
- **More legs meant more risk, not less.** At one contract per leg, a straddle carries about 2x the gamma and vega of the ATM call, and a 20-delta strangle about 1.4x those of the ATM put (measured at entry). The volatility result is mostly that size difference.
- **The strangle's edge is its exits.** The ATM put never hit the 50% profit take or the stop in 101 round trips. Strangles hit the profit take 9 times (+$2,670) and the stop 4 times (−$1,827). The short side went from −$148 to +$2,632, with $2,324 of it from strangles closed in 2020-2021. The 5 best strangles made $1,933 of it.
- **The straddle doubled the long side's loss:** −$3,555 against −$1,913 for the same 30 entries, mostly in 2022-2024.

## Caveats
- In-sample: the idea builds on the short-only, trend-long-band and lower-delta results on this window.
- The structures are not risk-matched with the baseline (one contract per leg), so this tests the structure and its size together.
- Each leg fills separately at its own half-spread. A combo order would usually fill better.
- 1 of 102 strangles (early 2016) closed its legs separately: one leg had no mark and could not be filled for about two weeks, and the book went unhedged on those 14 days (about −$11).
- Small sample: 30 straddles; the strangle result rests on 9 profit takes and 4 stops.
- The spread model was fitted on calm 2026 quotes (the 2x run is the stress test). About 3.3% of scheduled times are skipped.

## Next step
Archive this card. The strangle half is worth its own card: for example, a gamma-matched 20-delta strangle against the ATM put on the VRP-band book, judged on net P&L and Sharpe at 1x and 2x. That card would need a pass bar set before any run.
