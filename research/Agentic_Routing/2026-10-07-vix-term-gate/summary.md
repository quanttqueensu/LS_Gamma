# Summary: 2026-10-07-vix-term-gate

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-10-07 · **Verdict:** failed

## Result
The gate barely changes how often shorts are right, so it fails the precision test. Run on 2,492 daily forecasts (Oct 2015 to Aug 2025), IV = 0.83 × VIX. The VIX curve was inverted on 7.6% of days.

| | Live rule | Gated | Pass bar | |
|---|---|---|---|---|
| Short days | 370 | 308 (83% kept) | ≥ 50% kept | pass |
| Short precision | 71.6% | 72.4% | ≥ 76.6% | **fail** |
| Precision of the 62 removed days | | 67.7% | | |

The 62 days the gate removed were right 67.7% of the time, only 4 points worse than an average short day. So removing them hardly moves precision.

## Trials
One run (trial 1). The code was first checked on a coarse setting (every 40th day) without logging a run, and only the output shape was printed. That check is not counted as a trial. The pass bar was not changed.

## What surprised you
**The gate removed the worst losses, even though precision hardly moved.** This was checked *after* seeing the result, so it is not part of the verdict:

| Short days | Mean IV − realized | Worst day | Losses > 10 pts | Sum of losing days |
|---|---|---|---|---|
| Live | +2.8 pts | −57.5 pts | 8 | −4.80 |
| Gated | +2.9 pts | −12.1 pts | 5 | −3.27 |
| Removed | +2.2 pts | −57.5 pts | 3 | −1.53 |

- The worst live short was 2020-02-28: IV about 33%, then SPY realized 91% over the next month. The VIX curve was inverted that day (VIX/VIX3M 1.34), so the gate skipped it. It also skipped the two worst days of March 2025.
- The gate cut total losing-day size by about a third and the worst day from 57.5 to 12.1 points, while the average edge stayed the same.
- Many inverted days are *good* shorts. Right after a spike, IV is high and realized vol often calms down. In 2020, 12 of the 13 removed days were right. That's why precision is the wrong yardstick for a stress filter: it counts a 57-point loss the same as a 1-point loss.

## Caveats
- The tail finding rests on very few events: 3 big losses, two of them in the same week of March 2025. It is a reason for a new test, not a result.
- IV is approximated as 0.83 × VIX. At 1.0 × VIX the conclusion is the same: precision is 81.6% live vs 82.1% gated, and the 140 removed days were right 77.9% of the time.
- IV − realized is not trading P&L. It ignores the price path, hedging, costs and stops. A real short put could hit its 1× credit stop before the month's realized vol is known, which would shrink the tail the gate protects against.
- Overlapping 21-day windows: 370 short days are far fewer independent trades.

## Next step
Archive this card, since it failed its pre-set bar. Two follow-ups:
1. **Re-test the gate on a tail-risk metric, set in advance.** For example: *the gate cuts the worst-5% short outcome (expected shortfall of IV − realized) by at least 30%, while keeping at least 75% of short days and not lowering mean edge.* Use a fresh card, and keep the hold-out untouched.
2. **Get real P&L.** Both experiments so far use IV − realized as a stand-in. A short-put backtest with stops and daily hedging on historical option prices (R2 trades, ATM IV backed out via put-call parity) would show whether the gate's tail protection survives the stops. This is a bigger analyst project.
