# Summary: 2026-10-07-vix-gate-tail

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-10-07 · **Verdict:** failed (on the days-kept rule; the tail cut held out of sample)

## Result
On the unseen 2006–2015 test period, the gate cut the tail as predicted and raised the edge per trade. But it skipped 35% of short days, more than the 25% the card allowed, so it fails one of the four tests. Test period: 2006-08-01 to 2015-09-30, IV = 0.83 × VIX.

| | Live rule | Gated | Pass bar | |
|---|---|---|---|---|
| Expected shortfall (worst 5%) | −12.6 pts | −8.6 pts (32% cut) | ≥ 30% cut | pass |
| Short days | 461 | 299 (65% kept) | ≥ 75% kept | **fail** |
| Mean edge per traded day | +1.3 pts | +1.6 pts | not lower | pass |
| Gated short days | | 299 | ≥ 30 | pass |

Other numbers, not part of the bar:

| | Live rule | Gated |
|---|---|---|
| Worst day | −29.3 pts | −16.2 pts |
| Losses over 10 pts | 7 | 2 |
| Precision | 66.8% | 71.2% |
| Total edge (sum over days) | 6.12 | 4.92 (−20%) |

## Trials
One run (trial 1). The code was first checked on a coarse setting (every 40th day) without logging a run, and only the output shape was printed. That check is not counted as a trial. The pass bar was not changed.

## What surprised you
- **The tail result replicated on data nobody had looked at.** The gate skipped the worst test-period short (2008-10-10, −29.3 pts) and the three worst days of the July–August 2011 US downgrade (about −27 pts each). Five of the seven losses over 10 points were removed. The reference period (2015–2025, where the idea came from) shows the same picture: ES −12.3 to −7.9 pts, worst day −57.5 to −12.1 pts.
- **The days-kept rule failed because of 2007–2008.** The VIX curve stayed inverted for long stretches then, and 93 of the 162 skipped days fall in those two years. Those skipped days were a mixed bag: right 55–59% of the time, with roughly zero total edge. In early 2009 the skipped days were mostly losers (16% right).
- **The gate can't catch a crash that comes out of calm.** The two worst kept days were in April 2010, before the flash crash, when the curve was still upward sloping (VIX/VIX3M about 0.85–0.88).
- **The trade-off is clear.** The gate gives up about 20% of total edge, roughly a third fewer trades, for about a third less tail loss, and each trade it keeps is slightly better.

## Caveats
- IV is approximated as 0.83 × VIX, and that ratio comes from 2026 snapshots. Skew in 2006–2015 was different, so the proxy is rougher here. At 1.0 × VIX the gate would pass all four tests (ES cut 43%, 81% of days kept, edge per day up), but that is reported only and doesn't change the verdict.
- IV − realized is not P&L. The live short put has a 1× credit stop, which would cap some of these tail losses on its own. Whether the gate still adds value next to the stop needs an option-price backtest.
- The tail rests on a handful of episodes: 2008, 2011 and 2020. Overlapping 21-day windows mean consecutive days are close to the same trade.

## Next step
Don't promote yet, but don't archive the idea. The pre-set bar failed only on how many days the gate skips, and the tail protection held up out of sample. Whether giving up about 20% of total edge for about a third less tail loss is worth it is a PM risk decision, not something to re-test on this data.

Before any live change, test it on real P&L: a short-put backtest with the live stops and daily hedging, with and without the gate, priced from historical options (R2 SPY trades, ATM IV via put-call parity). If the gate still cuts drawdowns after stops, build it as a `SIGNALS` wrapper and run it in shadow mode.
