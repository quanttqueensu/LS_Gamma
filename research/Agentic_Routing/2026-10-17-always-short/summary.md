# Summary: 2026-10-17-always-short

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-17 · **Verdict:** failed (tail guard only)

Full report: [2026-10-17-always-short.pdf](2026-10-17-always-short.pdf)

## Result
On the 25-delta short-put book with the 10-share hedge band, being short every day regardless of the VRP signal (`always25`) beat the signal-timed book on every P&L check, at both spreads and in both halves. It failed the pre-registered tail guard: daily ES was 1.68x the reference's at 1x and 1.69x at 2x. Development window 2014-06-02 to 2024-12-31. Reference: the registered `2026-10-17-otm-put/put25` runs.

| Check (`always25` vs `put25`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | +$1,316 vs +$180 | +$862 vs −$273 | pass |
| Net P&L, 2014-06 to 2019-12 | +$553 vs −$280 | +$371 vs −$410 | pass |
| Net P&L, 2020-01 to 2024-12 | +$763 vs +$460 | +$491 vs +$137 | pass |
| abs ES 5% ≤ 1.10 × reference | 121.2 (limit 79.2) | 123.8 (limit 80.5) | **fail** |
| Round trips (event floor ≥ 30) | 187 | | met |

It is the first book in the desk's backtests with positive net P&L at 2x spreads. Max drawdown is $2,041 against $1,237 for the timed book ($3,027 for the live baseline). `always_atm` (sensitivity, ATM put) lost: −$845 at 1x and −$3,812 at 2x, paying $2,967 in spreads against $453.

## Trials
4 trials (2 variants × 1x and 2x, one run at commit 4e3e599) plus the baseline's 2. The reference was reused from `2026-10-17-otm-put` (2 trials, not rerun). After the run, the exposure chart's line styles were fixed and the figures rebuilt with `--report-only`, adding no trials. The pass bar was not changed; the PM chose before the run to keep the ES limit at 1.10x.

## What surprised you
- **Sitting out cost more than it saved.** Before costs the rolling book earns about +$2,750 against +$1,183. In 2014-2017, when the signal was mostly flat (all of 2017), the rolling book made +$1,597 against −$66, more than the whole net gap (+$1,136); from 2018 to 2024 it is $527 behind. The archived v1 backtest pointed the same way, but it inspired this test, so that agreement is weak evidence.
- **The bigger tail is real.** Over the 798 intervals in which the timed book held a position, the rolling book's ES is −$158 against −$135, and it lost $431 where the timed book made $319 (the timed book's other −$139 is the cost of its 87 entries from flat). The rolling book made +$1,742 while the timed book was flat.
- **The signal fires after the move (corrected 2026-10-18).** The rolling book lost $2,879 in the 143 intervals just before the signal turned short: IV jumps, then the signal says short. After a short signal both books made money (+$506 rolling, +$1,034 timed). The timed book also took 58 of those IV jumps while still holding after an earlier signal: it lost $1,065 on them. Apart from those jumps, its holding after the signal ended made money. So the signal's short days were not bad days to be short. The first version of this summary said they were, because it lined each day's P&L up one day early. The timed book's weakness is sitting out calm stretches.
- **2022 roughly broke even** (+$16 at 1x) where the timed book lost $1,039: −$1,143 in the intervals where the timed book held a position (timed: −$1,102), +$1,117 in the rest.
- **The tail is spread over the stress years:** the worst 5% of days fall mostly in 2022 and 2020, then 2024, 2018 and 2023. The losing years are 2018 (February and December), 2019 and 2024; the worst day is −$677 on 2024-08-02 and the drawdown trough is the March 2020 crash.
- **The strike still matters:** the same rolling rule with the ATM put loses at both spreads.

## Caveats
- In-sample: the idea comes from the desk's review of the baseline signal and the archived v1 results (2015-2021, inside this window). The 2026-10-07 proxy test warned that shorting more often adds tail losses, and the tail here agrees.
- The result rests on the spread model's OTM-vs-ATM cost gap, fitted on two weeks of calm 2026 quotes.
- Always-short depends on the premium staying positive (about 70% of days in 2014-2024). One contract, $1 order minimum, 89 skipped month-end times; `always25` also logged 9 unfilled orders and 10 days without a delta or mark (2016 and 2019). 10 stops and 34 profit-takes.

## Next step
Not promoted: the pre-registered tail guard failed. The PM's risk call is whether a rolling book's tail is acceptable. Possible follow-ups, each with its own card:
- a risk-adjusted bar (e.g. P&L per unit of ES);
- a forecast that tracks calm regimes better, since the timed book's loss is the calm stretches it sits out. The trailing bias correction (`2026-10-07-garch-bias-correction`) and HAR on daily returns (`2026-10-16-har-signal`) already failed; HAR on intraday realized variance from the parity spot is untried (skipping the signal's short days is not supported: shorting after them made money);
- a 15-20 delta rolling put.
