# Summary: 2026-11-02-vrp-hedge

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-vrp-hedge.pdf](2026-11-02-vrp-hedge.pdf)

## Result
On the 35% stress-sized `hedged` put book, leaving a new put unhedged for its whole life when VRP at entry was above 2 vol points (`vrp2`) did not beat always hedging. It failed 3 of the 5 checks at both spreads. Development window 2014-06-02 to 2024-12-31; reference: the registered 2026-10-22 `hedged` runs.

| Check (`vrp2` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $114,100 vs $121,482 | $87,924 vs $101,172 | fail |
| Net P&L, 2014-06 to 2019-12 | $54,493 vs $49,132 | $44,526 vs $42,687 | pass |
| Net P&L, 2020-01 to 2024-12 | $59,608 vs $72,350 | $43,398 vs $58,485 | fail |
| Sharpe ratio | 0.51 vs 0.52 | 0.39 vs 0.43 | fail |
| Max drawdown ≤ $87,500 | $73,622 | $78,839 | pass |
| Unhedged round trips (floor ≥ 20) | 45 | | met |

**Sensitivities** (reported only; they cannot pass this card):
- **`vrp1`** (cutoff 1 point) beat `hedged` on every check at both spreads:
  - net P&L: $149,178 and $146,791;
  - Sharpe: 0.65 and 0.64.
- **`vrp4`** (cutoff 4 points) made $141,397 and $120,623, but failed 2014-2019.

## Trials
6 trials (3 variants × 1x and 2x, one run at commit 954824c). The `vrp4` rows are tagged `-dirty` because three other experiments of the same batch were writing files in the same working tree; nothing of this experiment had changed. The reference and the baseline were reused. The commissions chart was fixed and rebuilt with `--report-only`, which adds no trials. The registry holds 98 trials. The pass bar was not changed.

## What surprised you
- **The timing works in the delta leg.**
  - In the always-unhedged 2026-10-22 book, the P&L of holding the put's delta in SPY earned 64% a year per dollar of delta for puts entered above 2 VRP points, against 9.5% for the rest. It was positive in all ten years with such entries.
  - `vrp2`'s 45 unhedged puts earned $56.9k of delta P&L (46% a year per dollar of delta) and on average $54 net per contract per round trip, against $7.8 for its hedged puts (pooled: $46.1 against $18.1).
- **Sizing and one path change gave it back.**
  - An unhedged put gets no hedge credit in the stress test, so it is smaller: 17.5 contracts against 25.2.
  - The put opened unhedged on 2 March 2020 was stopped on 9 March, three trading days before the hedged book's (12 March). The book re-entered into the crash and missed the 13 March 100-contract entry.
  - From 19 February to 30 April 2020, `vrp2` lost $7.6k while `hedged` made $21.7k. Outside that window `vrp2` was $21.8k ahead.
- **The cutoff matters a lot.** The result swings from −$7k to +$28k against `hedged` (1x), mostly from path dependence: only 117 of `vrp2`'s 208 round trips open at the same time as one of the hedged book's.

## Caveats
- **In-sample.** The idea came from the 2026-10-22 results. Before pre-registration, the desk saw the unhedged book's P&L per contract split at 2 VRP points.
- **Concentration.** The primary's shortfall comes from one March 2020 sequence.
- **Spread model.** Fitted on calm 2026 quotes, and fills of 20-100 contracts use the one-contract spread model.
- **Margin.** Not modelled.
- **Delta split.** An attribution (delta × spot change), not a hedged return.

## Next step
Archive this card. Don't promote `vrp1` from it: it was a sensitivity, and the cutoff results look like path noise.

A follow-up would need its own card, for example:
- keep the book's size and change only the hedge for high-VRP puts;
- or use VRP to set a partial hedge ratio.

Either way, the hold-out would be the real test.
