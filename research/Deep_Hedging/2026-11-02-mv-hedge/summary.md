# Summary: 2026-11-02-mv-hedge

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-mv-hedge.pdf](2026-11-02-mv-hedge.pdf)

## Result
On the 35% stress-sized `hedged` put book, hedging each put to its delta plus a Hull-White-style vega term (`mv`: vega × β / S, β = trailing 1-year slope of daily VIX-point changes on SPY returns) cut the daily tail and the drawdown, but cost more P&L than the $5,000 allowed. Development window 2014-06-02 to 2024-12-31; reference: the registered 2026-10-22 `hedged` runs.

| Check (`mv` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| ES 5%, full window | −$2,828 vs −$3,016 | −$2,871 vs −$3,094 | pass |
| Max drawdown, full window | $41,112 vs $70,362 | $41,119 vs $75,488 | pass |
| Net P&L not below `hedged` − $5,000 | $104,049 vs $121,482 | $79,425 vs $101,172 | fail |
| Round trips (floor ≥ 30) | 193 | | met |

Other numbers:
- **Sharpe:** 0.42 against 0.52 at 1x; 0.33 against 0.43 at 2x.
- **By half (1x):** 2014-2019 $15.8k against $49.1k; 2020-2024 $88.3k against $72.3k.
- **Sensitivity `mv_half`** (half the term): $55,966 / $29,367, Sharpe 0.29 / 0.15, max drawdown $44,012 / $54,028.

## Trials
4 trials (2 variants × 1x and 2x, one run of `experiment.py`). The `hedged` reference and the baseline were reused, not rerun. The `mv` 1x row is tagged 79b09a1-dirty and the other three 3568520-dirty: other cards of the same batch were pre-registered during the run, with uncommitted files in the shared working tree. The engine, `configs/backtest.toml` and this card's files are unchanged between the pre-registration (3ab834b) and both tags. The pass bar was not changed.

## What surprised you
- **The extra shares interact with the exit rules.** The stop and the profit-take include hedge P&L, and the vega term adds about 3-16 short shares per contract.
  - In falls, puts hit the 50% profit-take more often: 42 exits for $252.3k, against 25 for $148.3k.
  - Stops were fewer: 4 for −$14.4k, against 8 for −$97.9k.
  - In rallies, puts ran to the 7-DTE exit: time exits lost $122.4k, against +$52.9k for the reference.
  - `mv` beat the reference only in 2018, 2020 and 2022.
- **March 2020 decides the tail result.** From 19 February to 30 April 2020, `mv` made $89.4k against $21.7k. It was never stopped, and its 55- and 120-contract puts hit the profit-take. Outside that window it made $14.7k against $99.8k. Only 97 of its 193 round trips opened at the same time as the reference's.
- **The "minimum-variance" hedge raised daily variance:** standard deviation $1,515 against $1,446 at 1x.
- **`mv_half` was not between the two.** It made the least ($56.0k), because a different March 2020 path made only $11.1k in that window. This points to path dependence, not the hedge ratio.

## Caveats
- **In-sample:** the idea is from the 2026-09-27 leverage-effect report; the book was chosen after its 2014-2024 results. Before pre-registration, testing the report code showed the median β (about −142).
- **One crash:** most of the lower drawdown comes from one path through February-April 2020.
- **Approximations:**
  - VIX stands in for the put's own IV change.
  - β is a walk-forward VIX regression, not Hull & White's fitted coefficients.
  - Stress sizing ignores the extra shares.
- **Model limits:**
  - Spread model fitted on calm 2026 quotes; fills of up to 120 contracts use the one-contract model.
  - Margin not modelled.
  - About 3.3% of scheduled times skipped.

## Next step
Archive this card. A follow-up would need its own card, and should separate the hedge from the exits. Two options:
- measure the stop and the profit-take on the option alone;
- fit β on the put's own IV instead of VIX.
