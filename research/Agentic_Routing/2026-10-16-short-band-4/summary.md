# Summary: 2026-10-16-short-band-4

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed

Full report: [2026-10-16-short-band-4.pdf](2026-10-16-short-band-4.pdf)

## Result
On the short-only book, raising the short band from +2 to +4 vol points (`short_band = 0.04`) did not beat the +2 band on the pre-registered bar. It lost more at 1x over the full window, and in 2020-2024 at both spreads. It did better at 2x and in 2014-2019, mostly because it traded about half as often. Development window 2014-06-02 to 2024-12-31.

| Check (`band4` vs `short_only`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | −$950 vs −$774 | −$1,525 vs −$2,351 | fail 1x, pass 2x |
| Net P&L, 2014-06 to 2019-12 | −$237 vs −$875 | −$355 vs −$1,261 | pass |
| Net P&L, 2020-01 to 2024-12 | −$713 vs +$101 | −$1,171 vs −$1,090 | fail |
| abs ES 5% ≤ 1.10 × reference | 61.7 (limit 94.1) | 64.1 (limit 101.7) | pass |
| Round trips (event floor ≥ 30) | 53 | | met |

`band3` (sensitivity, not judged) lost less than the reference: −$546 at 1x and −$1,658 at 2x. But at 1x it was $20 short in 2020-2024 (+$81 vs +$101).

## Trials
4 trials (2 variants × 1x and 2x, one run at commit 6b9adb9) plus the baseline's 2. The `short_only` reference was reused from `2026-10-16-short-only` (2 trials, not rerun). The pass bar was not changed.

## What surprised you
- **Edge per trade fell instead of rising.** Round trips fell from 100 to 53, and the median VRP at entry rose from 2.9 to 4.7 vol points. But net P&L per round trip fell from −$5.6 to −$9.6 at 1x, and was about the same at 2x (−$20.2 vs −$21.2).
- **The band also moves the exit.** A short closes after 3 straight days at or below the band. So at +4, a short closes when VRP drifts back to +2 to +4, where the reference keeps holding. The 17 `band4` trades that opened on the same day as a reference trade were held 8.4 days instead of 14.1, and all of them closed on the flat exit. They made −$858 before commissions, against +$194 for the same entries in the reference.
- **In the reference, entries above +4 did earn more,** +$44 net per trade at 1x over 22 trades. But 5 of those trades made $954 of the $963, so the selection effect rests on very few trades.
- **The 2x pass is cost avoidance.** In the 1x bridge, round-trip P&L is −$384, commissions save +$438 and the unwind residual is −$230, giving −$176. At 2x it is +$610 + $438 − $222 = +$826. The jump comes from paying half as many spreads.
- **Unwind noise moves `band3` most.** Its hedge-flattening fill gap is −$1,083, mostly in 2020 and 2022. Without it, `band3`'s round trips net +$609 at 1x, against −$562 for the reference.

## Caveats
- In-sample: the idea comes from the 2026-10-16 desk discussion of the baseline on this window. The VRP-bucket breakdown is also in-sample.
- Few events: 53 round trips and only 5 time exits for `band4`. With one position slot, only 17 of its trades can be matched to the reference.
- ES is measured on daily equity including flat days, so a book that is out of the market more has a smaller ES almost by construction.
- One contract with a $1 order minimum favours books that trade less. The spread model was fitted on calm 2026 quotes. Month-end R2 days are missing (89 skipped times).

## Next step
Keep the +2 short band. A possible follow-up, needing its own card, a research-only engine flag, and in-sample: separate the entry band from the flat-exit band (enter above +4, count flat days only below +2). That would test the selection effect without the earlier exits.
