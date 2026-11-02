# Summary: 2026-11-02-lower-delta

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** passed (in-sample; hold-out not run)

Full report: [2026-11-02-lower-delta.pdf](2026-11-02-lower-delta.pdf)

## Result
On the 35% stress-sized `hedged` book, selling the 20-delta put (`put20`) instead of the 25-delta put passed every pre-registered check at 1x and 2x spreads. The reference is the registered `2026-10-22-stress-sized-puts/hedged`; the development window is 2014-06-02 to 2024-12-31.

| Check (`put20` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $149,893 vs $121,482 | $133,123 vs $101,172 | pass |
| Net P&L, 2014-06 to 2019-12 | $59,301 vs $49,132 | $50,199 vs $42,687 | pass |
| Net P&L, 2020-01 to 2024-12 | $90,592 vs $72,350 | $82,924 vs $58,485 | pass |
| ES 5% within 1.10x | −$2,457 vs −$3,016 | −$2,489 vs −$3,094 | pass |
| Max drawdown ≤ $87,500 | $48,435 | $51,352 | pass |
| Round trips (floor ≥ 30) | 192 | | met |

- **Sharpe:** 0.78 against 0.52 at 1x; 0.69 against 0.43 at 2x.
- **Sensitivity `put15`** (15-delta): $113,809 / $110,501. It failed the same bar: below the reference over the full window at 1x and in 2014-2019 at both spreads.

## Trials
- 4 trials: 2 variants × 1x and 2x, one run of `experiment.py`. The reference and the baseline's 2 were reused, not rerun.
- **`-dirty` tags:** the runs are tagged `af47198-dirty` and `3568520-dirty`. Those are later pre-registration commits of other cards in the same batch, and both contain this card's pre-registration (bc7506b). Code and configs did not change; the flag comes from other cards' uncommitted files in the shared working tree.
- One chart label fixed and the figures rebuilt with `--report-only`; no new trials.
- The pass bar was not changed.

## What surprised you
- **The strike made no difference on the same days.** Only 92 of the reference's 182 entries fall on the same day as a `put20` entry. On those days the two books earned the same: `put20` $70.0k against $71.7k, $31.0 against $31.2 per contract. The whole lead is in trades entered on different days.
- **The stress budget sizes every delta alike:** 25.4, 25.2 and 25.9 contracts on average. In a 20% drop at 60% IV all three puts are deep in the money, so a lower delta doesn't buy more contracts. It only collects less premium per contract: about $265, $210 and $153.
- **The lead is mostly August 2015.** `put20` was stopped on Friday 21 August 2015 and re-entered on the morning of 24 August, the flash-crash day, with 104 contracts. It took profit two days later for +$14.9k, about half the lead; the rest of August's gain came from being stopped on the Friday rather than at Monday's open.
  - The 2015 lead was fully given back by 2021 (−$0.3k at end-2021) and rebuilt in 2022-2024.
  - August 2015 alone gives $26.5k of the $28.4k lead at 1x.
  - Without that month the books are close: $136.9k against $135.0k at 1x, $120.5k against $115.4k at 2x.
- **Other gains are path accidents too.**
  - March 2020: `put20` avoided two reference stops, which explains the smaller drawdown, but it missed the 13 March 100-contract sale.
  - June 2022: a different roll date avoided a −$15.9k put.
  - `put20` is ahead in only 59 of 127 months.

## Caveats
- **In-sample.** The idea comes from the 2026-10-22 deep research, written after the desk's 25-delta, 35-delta and ATM results on 2014-2024. Before pre-registration, Claude saw the reference's aggregate trip and cost figures while testing the reporting code.
- **Concentration.** One month gives 93% of the 1x lead, and the result depends on the roll calendar.
- **Spread model.** Fitted on calm 2026 quotes. A 104-contract fill on a crash morning uses the one-contract spread model.
- **Stale sizing on 24 August 2015.** That entry was sized on the 15-minute-stale decision view near the crash low; at the fill view the same rule gives 87 contracts. The engine works as designed, and a live run faces the same lag.
- **Stress model and margin.** The stress model is Black-Scholes with no IV shock above max(60%, IV); margin is not modelled.
- **Data gaps.** About 3.3% of scheduled times are skipped.

## Next step
The PM decides on a hold-out run of `put20` (`/run-experiment-with-report holdout 2026-11-02-lower-delta`). Its reference is the 2026-10-22 `hedged` book's hold-out run, which is that card's single hold-out look, so decide both together. Expect the in-sample margin to shrink: on shared entry days the 20-delta put earned the same per contract.
