# Summary: 2026-11-02-slope-sizing

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-slope-sizing.pdf](2026-11-02-slope-sizing.pdf)

## Result
The test scaled the 35% stress budget of the `hedged` put book from 1.5x in the steepest VIX contango (VIX/VIX3M at its one-year low) to 0.5x at the most inverted. It failed every P&L check at 1x and 2x and passed the tail and drawdown checks. The primary is `slope`; the reference is the registered `2026-10-22-stress-sized-puts/hedged`; the window is 2014-06-02 to 2024-12-31.

| Check (`slope` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $100,574 vs $121,482 | $78,318 vs $101,172 | fail |
| Net P&L, 2014-06 to 2019-12 | $43,556 vs $49,132 | $34,608 vs $42,687 | fail |
| Net P&L, 2020-01 to 2024-12 | $57,018 vs $72,350 | $43,710 vs $58,485 | fail |
| ES 5% within 1.10x | −$2,471 vs −$3,016 | −$2,565 vs −$3,094 | pass |
| Max drawdown ≤ $87,500 | $42,017 | $46,035 | pass |
| Round trips (floor 30) | 182 | | met |

The book was safer, not more profitable:
- **Sharpe:** 0.64 against 0.52 (1x); 0.49 against 0.43 (2x).
- **Max drawdown:** $42k against $70k (1x).
- **Contracts per entry:** about the same on average (24.7 against 25.4), with a maximum of 52 instead of 100.

Sensitivities:
- `slope_light` (half the tilt) landed between the two books on every headline metric.
- `slope_reverse` (the opposite tilt) matched `hedged` at 1x ($121.0k) and beat it at 2x ($119.0k), with a lower Sharpe and a 2x drawdown of $84.2k, close to the budget.

## Trials
6 trials (3 variants × 1x and 2x, one run of `experiment.py`), plus the baseline's 2. The `hedged` reference was reused, not rerun. The registry holds 98 trials after the four 2026-11-02 cards. The two `slope_reverse` rows are tagged `-dirty`, because a parallel experiment's reporting script was being edited during the run. The engine, configs and this card's files were unchanged. The pass bar was not changed.

## What surprised you
- **The tilt cut the book's best trades by about 40%.** VIX/VIX3M was at or near its one-year high in early 2020, so all five entries from 26 February to 17 April 2020 were sized at 0.5-0.67x. The 100- and 71-contract entries became 50 and 40. Those round trips made $14.3k instead of $22.9k.
- **2020 explains about $9.7k of the gap at 1x.** The rest is spread over 2015, 2019, 2022 and 2014 (−$4.7k, −$5.1k, −$4.4k, −$2.1k), partly offset by gains in 2016-2018 and 2023.
- **The curve didn't sort P&L per contract.** In the `hedged` book, the steepest-contango tercile made $24.3 per contract against $6.1 for the flattest. But the standard errors are $14-33, and the rank correlation is −0.004. The flattest tercile's dollars were the largest ($62.8k), from a few big high-IV entries.

## Caveats
- **In-sample:** the idea is from the literature (Johnson 2017) via the 2026-10-31 report. The book is the 2026-10-22 primary, chosen after its results. Earlier desk gate tests had already shown that skipping shorts on an inverted curve removed profit.
- **One episode:** March 2020 dominates the comparison.
- **Model limits:**
  - Black-Scholes stress model, with no vol shock above 60% IV.
  - Spread model fitted on calm 2026 quotes.
  - Margin not modelled.
  - About 3.3% of scheduled times skipped.

## Next step
Archive the term-structure tilt as a profit signal. Its risk-cutting effect looks like a smaller fixed budget. The 15% and 25% budgets the PM asked for on 2026-10-22 are the cleaner test of that.
