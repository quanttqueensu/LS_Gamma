# Summary: 2026-10-16-no-flat-exit

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed

Full report: [2026-10-16-no-flat-exit.pdf](2026-10-16-no-flat-exit.pdf)

## Result
On the short-only book, removing the flat-signal exit (`flat_days = 999`) did not beat the 3-day flat exit on the pre-registered bar. It helped slightly at 1x, lost at 2x, and was worse in 2014-2019 at both spreads. Development window 2014-06-02 to 2024-12-31.

| Check (`no_flat` vs `short_only`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | −$676 vs −$774 | −$2,388 vs −$2,351 | pass 1x, fail 2x |
| Net P&L, 2014-06 to 2019-12 | −$1,023 vs −$875 | −$1,540 vs −$1,261 | fail |
| Net P&L, 2020-01 to 2024-12 | +$347 vs +$101 | −$849 vs −$1,090 | pass |
| abs ES 5% ≤ 1.10 × reference | 91.2 (limit 94.1) | 99.8 (limit 101.7) | pass |
| Time exits (event floor ≥ 20) | 76 | | met |

`flat10` (sensitivity) was worse than both at both spreads: −$931 at 1x and −$2,514 at 2x.

## Trials
6 trials (3 variants × 1x and 2x, one run) plus the baseline's 2. `short_only` repeats `2026-10-16-short-only/short_only` with identical numbers, so the same test is now registered 4 times across the desk. The pass bar was not changed.

## What surprised you
- **The decay gain is real.** Round-trip P&L before commissions rose 3.7x, from +$318 to +$1,166 at 1x, with holds of about 24 days instead of 11. That figure is already net of spreads.
- **The costs grew instead of falling.** There were 24 fewer round trips, but hedge orders rose from 770 to 1,188 (+$418): a short held longer is hedged on more days, and each small hedge pays the $1 minimum. The 1x bridge is +$848 more round-trip P&L, −$410 more commissions and −$340 more unwind cost, giving +$98. At 2x it is −$37.
- **Most of the unwind cost is noise.** It is the gap between the fill-window spot and the decision spot on the orders that flatten the hedge, and a few days in 2020 and 2022 dominate it. So both margins (+$98 at 1x, −$37 at 2x) are inside the noise. The change is roughly neutral on this cost structure.
- **In-the-money closes cost more.** Holding to 7 DTE ends more shorts in the money (32% vs 27%). An in-the-money round trip costs about $56 in option spread, against about $6 out of the money. This is already inside the round-trip P&L.
- **The years cut both ways.** At 1x it did better in 2014, 2019, 2020, 2022 (−$1,165 vs −$1,433) and 2024, and worse in 2015-2016, 2018, 2021 and 2023.

## Caveats
- In-sample: the idea came from the baseline's exit-reason breakdown on this window.
- One contract: the $1 order minimum turns longer holds into many small hedge orders. At larger size this matters less.
- The spread model was fitted on calm 2026 quotes, and the in-the-money spread tier drives part of the cost. Month-end R2 days are missing (89 skipped times).

## Next step
Keep the 3-day flat exit. A follow-up worth its own card, also in-sample: `no_flat` combined with the 10-share hedge band, which cuts exactly the cost that grew here. Compare it against short-only plus the 10-share hedge band (queued as "short-only + hedge band").
