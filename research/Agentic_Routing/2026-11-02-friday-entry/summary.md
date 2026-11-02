# Summary: 2026-11-02-friday-entry

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-friday-entry.pdf](2026-11-02-friday-entry.pdf)

## Result
The test: on the 35% stress-sized `hedged` book from 2026-10-22, allow new puts only on Fridays, so a book closed midweek by its profit-take or stop waits for Friday to re-enter. It failed: full-window and 2020-2024 net P&L fell at both spreads. Development window 2014-06-02 to 2024-12-31.

| Check (`friday` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $111,315 vs $121,482 | $90,120 vs $101,172 | fail |
| Net P&L, 2014-06 to 2019-12 | $53,677 vs $49,132 | $44,433 vs $42,687 | pass |
| Net P&L, 2020-01 to 2024-12 | $57,638 vs $72,350 | $45,688 vs $58,485 | fail |
| ES 5% within 1.10x | −$2,803 vs −$3,016 | −$2,897 vs −$3,094 | pass |
| Max drawdown ≤ $87,500 | $32,301 | $38,232 | pass |
| Midweek profit or stop exits (floor ≥ 25) | 28 | | met |

**Sensitivity `tuesday_roll`** (holds the expiring put to the Tuesday of expiry week; it cannot pass this card):
- net P&L: $130,874 at 1x, $111,414 at 2x;
- Sharpe 0.72 at 1x;
- max drawdown $47,634 at 1x ($55,508 at 2x);
- it lost to the reference in 2020-2024 at both spreads.

## Trials
4 trials (2 variants × 1x and 2x, one run; the registry tags it 954824c, the batch's last pre-registration commit, which contains this card's bc742fd), plus the baseline's 2. The reference `2026-10-22-stress-sized-puts/hedged` was reused, not rerun. The pass bar was not changed.

## What surprised you
- **The smaller drawdown is one path through March 2020.**
  - `friday` re-entered with 46 contracts on 28 February. That put was never stopped, so the book avoided two stops the reference took.
  - It also missed most of the rally that the reference's 100-contract put (sold 13 March) caught.
  - Its drawdown was $32k against $70k, but its P&L from 15 February to 30 April 2020 was $15.7k against $21.6k.
- **Outside that window the rule still trails slightly:** $95.6k against $99.9k at 1x. The yearly differences are a few thousand dollars and change sign, so there is no clear effect either way.
- **The weekend pattern doesn't become a rule.** `friday` earned more over Friday-to-Monday intervals but lost more from Thursday to Friday, almost all of it on 19-20 March 2020.
- **`tuesday_roll` is lumpy.** Against the reference: +$24.7k in 2015, mostly August, and −$30.4k in 2020. It also skipped hedges more often near expiry: 35 missing deltas against 15 for the reference.

## Caveats
- **In-sample:** the idea came from the 2026-10-31 report's check on `always25`, and the book was chosen after the 2026-10-22 results. Before pre-registration, the reference's P&L by interval was seen while testing the report code.
- **One crash decides the drawdown result.**
- **Fewer real waits than counted:** 7 of the 28 midweek exits were on Thursdays; after 6 of them the book re-entered on Friday, as the reference would have.
- **Spread model:** fitted on two weeks of calm 2026 quotes. Large March 2020 fills use the same model as small ones.
- **Data gaps:** 3.3% of scheduled times are skipped.

## Next step
Archive Friday-only entry. A Tuesday roll would need its own card. That card should split out March 2020 and check the near-expiry hedge gaps before anything else.
