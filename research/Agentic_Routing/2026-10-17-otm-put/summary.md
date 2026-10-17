# Summary: 2026-10-17-otm-put

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-17 · **Verdict:** failed (one of eight checks, by $60)

Full report: [2026-10-17-otm-put.pdf](2026-10-17-otm-put.pdf)

## Result
On the short-only book with the 10-share hedge band, selling a 25-delta put (`put25`) instead of the ATM put beat the ATM book on seven of eight pre-registered checks. It failed one: 2020-2024 at 1x, +$460 against +$521. Development window 2014-06-02 to 2024-12-31. Reference: the registered `2026-10-16-short-only-band10/band10` runs.

| Check (`put25` vs `band10`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | +$180 vs −$170 | −$273 vs −$1,847 | pass |
| Net P&L, 2014-06 to 2019-12 | −$280 vs −$691 | −$410 vs −$1,180 | pass |
| Net P&L, 2020-01 to 2024-12 | +$460 vs +$521 | +$137 vs −$667 | **fail 1x**, pass 2x |
| abs ES 5% ≤ 1.10 × reference | 72.0 (limit 96.2) | 73.2 (limit 104.8) | pass |
| Round trips (event floor ≥ 30) | 105 | | met |

It is the first book in the desk's backtests with positive net P&L over the full window at 1x, and has the smallest maximum drawdown so far ($1,237 against $2,010). Its worst day is −$399 against −$727. `put35` (sensitivity) was −$186 at 1x, slightly worse than the ATM book, and −$1,047 at 2x, in between.

## Trials
4 trials (2 variants × 1x and 2x, one run at commit 06dbdc8) plus the baseline's 2. The reference was reused from `2026-10-16-short-only-band10` (2 trials, not rerun). Two charts were tidied after the run (colours, legend) and the figures rebuilt with `--report-only`, adding no trials. The pass bar was not changed.

## What surprised you
- **It is not the skew premium.** Before costs the 25-delta book earns less: +$1,183 against +$2,102 for the ATM book (0.56x). The 25-delta put has half the premium and delta of the ATM put but about 0.8x its vega, so edge per unit of vol exposure fell.
- **The whole gain is cost.** Spreads paid fall from $1,677 to $453 at 1x, because a cheaper option has a smaller spread in dollars and rarely ends deep in the money, where closing is expensive. Commissions fall a little ($595 to $550). The ATM book spent $2,272 in costs to earn $2,102 before costs; the 25-delta book spent $1,003 to earn $1,183.
- **The smaller credit changes the exits.** There are 7 profit-takes (+$1,194) and 4 stops (−$1,705, the largest loss bucket in either book), against 0 and 1 for the ATM book.
- **The failed half comes from two years.** 2023 and 2024 cost −$430 together at 1x, where the ATM put collected more. 2022 gained +$366.

## Caveats
- In-sample: the idea comes from the PM's review of all 2026-10-16 results on this window.
- The result rests on the spread model's cost gap between ATM and OTM puts, fitted on about two weeks of calm 2026 quotes. Checking that against real paper fills is the most useful next data step.
- OTM put prices come from the per-expiry smile fit. The traded 25-delta strikes sit a median 4.0% below spot (at most about 11%), inside the fit.
- Few stop and profit-take events (4 and 7). One contract with a $1 order minimum. Month-end R2 days are missing (89 skipped times).

## Next step
Not promoted: the pre-registered bar failed, and it is not changed after the fact. The strongest follow-ups, each needing its own card and adding trials:
- a 15-20 delta put, which the cost argument says should help again;
- two 25-delta contracts against one ATM contract (matched premium and delta, about 1.6x the vega);
- a check of real paper-account fills against the spread model.
