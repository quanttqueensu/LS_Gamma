# Summary: 2026-10-16-short-only-band10

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** passed (in-sample; the hold-out run is still to do)

Full report: [2026-10-16-short-only-band10.pdf](2026-10-16-short-only-band10.pdf)

## Result
Short-only plus the 10-share hedge band (`band10`) beat short-only alone on every check, at both 1x and 2x spreads. Development window 2014-06-02 to 2024-12-31; reference = the registered `2026-10-16-short-only/short_only` runs.

| Pass bar | 1x: band10 vs short_only | 2x: band10 vs short_only | |
|---|---|---|---|
| Net P&L, full window | −$170.4 vs −$773.8 | −$1,847.5 vs −$2,351.4 | pass |
| Net P&L, 2014-06 to 2019-12 | −$691.0 vs −$875.1 | −$1,180.1 vs −$1,260.9 | pass |
| Net P&L, 2020-01 to 2024-12 | +$520.5 vs +$101.3 | −$667.4 vs −$1,090.4 | pass |
| abs(ES 5%) ≤ 1.10 × reference | 87.4 vs 85.5 (1.02×) | 95.3 vs 92.4 (1.03×) | pass |
| Event floor: hedge orders cut ≥ 20% (1x) | 395 vs 770 (49% cut) | | met |

Other numbers: Sharpe −0.03 vs −0.15 at 1x and −0.32 vs −0.42 at 2x. Max drawdown is $2,010 vs $2,220 at 1x and $2,806 vs $3,222 at 2x. Both books have 100 round trips. The book still loses money over the full window.

Where the gain comes from (1x / 2x):
- **Hedge commissions saved:** +$375 / +$375. This part is mechanical: 375 fewer $1-minimum orders.
- **Gross round-trip P&L:** +$477 / +$378. Of this, +$361 at 1x is the share leg on the 99 matched trades, and +$116 is the one trade that changed.
- **Unattributed unwind residual:** −$248 / −$249. Almost all of it is one 73-share unwind after a stop on 2015-08-24, which filled about $4 a share from the decision spot.

## Trials
2 trials for this experiment (`band10` at 1x and 2x, one run of `experiment.py` at the pre-registration commit c2f7109, not dirty). The reference was reused from `2026-10-16-short-only` (2 trials, not rerun). Baseline trial 1 (2 trials) is shown in the charts for context. The pass bar was not changed.

## What surprised you
- **The two rules nearly add up.** The combined book gains $1,889 over the baseline at 1x. That is 84% of the two separate gains ($1,286 + $963), and 86% at 2x. The band is worth $603 here against $963 on the baseline book, because there are fewer small orders to drop (375 against 445).
- **The share-leg gain is diffuse.** On the 99 matched trips, 47 gain and 49 lose, and the median change is zero. The 13 time-exit trips give $254 of the $361. It looks like path P&L, not a mechanism, as in the hedge-band study.
- **The band moved one exit into a crash.** One short hit the stop on the morning of 2015-08-24 instead of closing on a flat signal three days later. The trade itself lost less. Its unwind then cost $303 in fill gap, so 2015 is $19 worse at 1x and $124 worse at 2x.
- **Hedging is identical at 1x and 2x.** The cut in hedge orders (770 to 395) matches the band's cut on the baseline book.

## Caveats
- The idea comes from the desk discussion of the baseline and from the short-only and hedge-band results, all on this window. This is in-sample evidence, and only the hold-out can confirm it.
- The 2014-2019 margin at 2x is thin ($81). About 60% of the 1x gain is share-path P&L that may not repeat.
- With one contract, the $1 minimum dominates. With more contracts the fee saving per contract shrinks.
- The spread model was fitted on about two weeks of calm 2026 live quotes. 3.3% of scheduled times are skipped (no month-end R2 days).
- Fills use trades in the 15 minutes after each 10:15 decision. On fast days the unwind gap is a few dollars a share, and one such day drives the residual.
- The reference was not rerun. Its config matches `band10` except `min_shares`, and an identical rerun under `2026-10-16-no-flat-exit` reproduced its equity exactly.

## Next step
Run `band10` once on the hold-out (2025-01-01 to 2026-07-10) against the hold-out baseline, on the card's hold-out bar: net P&L higher and |ES 5%| within 1.10× at 1x and 2x. If it holds, run it in shadow mode next to the live rules. The PM then decides on the two-line change (`[signal] long_band`, `[hedge] min_shares = 10`) in `configs/paper.toml`, with a decision record.
