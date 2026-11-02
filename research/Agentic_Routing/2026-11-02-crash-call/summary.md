# Summary: 2026-11-02-crash-call

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-crash-call.pdf](2026-11-02-crash-call.pdf)

## Result
On the 35% stress-sized `hedged` put book, also buying at-the-money calls with 0.5% of capital ($1,250) when VIX/VIX3M at the prior close was at least 1.1 (`crash11`: 8-14 DTE, held 5 trading days, delta-hedged with the book) did not cut the drawdown. It failed the drawdown check at both spreads. Development window 2014-06-02 to 2024-12-31; reference: the registered 2026-10-22 `hedged` runs.

| Check (`crash11` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Max drawdown less severe | $70,998 vs $70,362 | $76,514 vs $75,488 | fail |
| ES 5% less severe | −$2,998 vs −$3,016 | −$3,077 vs −$3,094 | pass |
| Net P&L not below hedged − $10,000 | $119,806 vs $121,482 | $98,891 vs $101,172 | pass |
| Crash calls opened (floor ≥ 10) | 14 | | met |

**Sensitivities** (reported only; they cannot pass this card):
- **`crash10`** (gate 1.0, 59 calls): −$6.9k at 1x and −$7.0k at 2x against `hedged`; drawdown $73.5k and $80.3k.
- **`crash11_30d`** (30-day call, 12 calls): met all three checks by small amounts. Drawdown $69.5k and $74.7k; P&L +$709 and +$581. All of the gain came in 2020.

## Trials
6 trials (3 variants × 1x and 2x, one run at commit 3568520), all tagged `3568520-dirty` because other cards of the same batch had uncommitted files in the shared working tree. The engine, configs and this card's files were unchanged. The reference was reused, not rerun. After the run, the charts were changed in the script only and rebuilt with `--report-only`, which adds no trials. The pass bar was not changed.

## What surprised you
- **The call is too small to matter.** It bought 14 calls of 1-4 contracts ($14.6k of premium in ten years), beside a put book of up to 100 contracts. Its whole effect was −$1.7k (1x) over the window.
- **It lost inside the drawdown window.** The reference's deepest drawdown runs from January 2018 to 17 March 2020.
  - The calls lost about $1.85k in 2018-2019 and gained only about $0.75k from 19 February to 30 April 2020, so the drawdown was $636 deeper at 1x.
  - Net of hedges, the calls lost in every year with entries except 2020.
- **A lower gate is worse.** At 1.0 the calls' own option P&L was +$5.2k (1x), but the shares hedging them lost $12.1k.
- **Per-trade attribution is unreliable for two positions at once.** The engine splits hedge shares across open positions, and the shared round-trip pairing matches by time only. So the call was measured by the equity difference against `hedged`. The puts are identical in every 1x run, which makes that difference exactly the calls and their hedges.

## Caveats
- **Hold length.** The engine holds the call for 5 weekdays, not 5 trading days: it counts business days without the exchange calendar. Over a holiday that is 4 trading days, which happened to 3 of `crash11`'s 14 calls (February and December 2018, New Year 2019) and 5 of `crash10`'s 59. One call (August 2015) was held 6 trading days because a month-end snapshot is missing. This deviates from the card's "5 trading days"; with 1-4 contracts it is unlikely to change the verdict, but that can't be shown without a rerun.
- **In-sample:** the idea comes from the 2026-10-07 report and the 2026-10-22 results. The gate's frequency was counted from the features file before pre-registration.
- **One episode:** March 2020 is the only crash where a call pays.
- **Path dependence:** at 2x, `crash10`'s puts diverge from the reference's from March 2022, because the call's hedge shares count in the put's P&L.
- **Report code:** the registry's `hold_days` for these rows uses the time-only pairing. The pass-bar metrics are unaffected.
- **Spread model:** fitted on calm 2026 quotes. Short-dated calls in a spike may cost more.

## Next step
Archive; don't run the hold-out. A meaningful crash hedge would have to be sized to the put book's crash loss, not to a premium budget, and that needs its own card. Separately, fix `metrics.pairs` to match by entry time and contract before any future multi-leg card.
