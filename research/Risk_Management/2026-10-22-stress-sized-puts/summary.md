# Summary: 2026-10-22-stress-sized-puts

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-22 · **Verdict:** passed (in-sample; the hold-out run is still to do)

Full report: [2026-10-22-stress-sized-puts.pdf](2026-10-22-stress-sized-puts.pdf)

## Result
Sizing the always-on 25-delta short put (`always25`) at every entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at 60%, stays within 35% of capital ($87,500) passed every check at 1x and 2x spreads. Primary `hedged` (the daily 10-share hedge) against the registered one-contract `always25`, development window 2014-06-02 to 2024-12-31.

| Check (`hedged` vs `always25`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $121,482 vs $1,316 | $101,172 vs $862 | pass |
| Net P&L, 2014-06 to 2019-12 | $49,132 vs $553 | $42,687 vs $371 | pass |
| Net P&L, 2020-01 to 2024-12 | $72,350 vs $763 | $58,485 vs $491 | pass |
| Net P&L above zero | $121,482 | $101,172 | pass |
| Max drawdown ≤ $87,500 | $70,362 | $75,488 | pass |
| Round trips (event floor ≥ 30) | 182 | | met |

Sensitivity variants (reported only, cannot pass this card):
- **`banded`** (Whalley-Wilmott band, 30 × √book gamma):
  - net P&L: $114,559 (1x) / $96,288 (2x);
  - Sharpe 0.61 against 0.52 for `hedged`;
  - max drawdown $48,744;
  - hedge commissions $1,040 against $2,868.
- **`unhedged`:**
  - net P&L: $253,839 / $239,831;
  - 75% of it at 1x ($190.4k) is the P&L of holding its option delta in SPY;
  - about $63.5k (1x) is left after removing it.

## Trials
6 trials (3 variants × 1x and 2x, one run at commit a515c6d, none `-dirty`), plus the baseline's 2. The `always25` reference was reused from `2026-10-17-always-short` (2 trials, not rerun). After the run, reporting tables and one chart were added to `experiment.py` and the figures were rebuilt with `--report-only`, which adds no trials. The pass bar was not changed.

## What surprised you
- **The rule sells the most when vol spikes.** Its stress scenario adds no vol shock once IV is above 60%, and a higher IV puts the 25-delta put further out of the money. So the stress loss per contract falls as IV rises, and notional at entry tracks IV (correlation 0.90 for `hedged`).
  - In March 2020 the hedged book sold 100 contracts (about 10x capital in notional) and then 71. Those two round trips made $61.3k of its $113.2k round-trip net.
  - Its entries below 15% IV lost $9.1k.
- **The March 2020 path was violent.** The hedged book fell from +$49.7k (19 February) to −$17.0k (17 March), then made $77.4k from 18 to 24 March. The market bottomed six trading days after the 100-contract entry.
- **Recent years are thin.** In 2023-2024, at 11-20 contracts, the hedged book made $5.0k at 1x and $2.2k at 2x. On the 2026-10-21 chain the rule would trade 8 contracts hedged, 7 banded or 6 unhedged (desk calculation).
- **Margin would have bound.** By a rough Reg-T estimate, the hedged book needed a median of $211k on $250k of capital, and more than $250k on 16 of 182 entries (up to about $637k). The unhedged book stayed at or below $136k.
- **Tiered vs Fixed.** By the card's rule, Tiered is recommended for the hedged book. On its 2023-2024 hedge orders (median 56 shares) it costs $291 against $418 under Fixed, 31% less, or about $64 a year. Tiered would cost the banded book more: its orders are larger (median 260 shares).

## Caveats
- **In-sample:** the idea comes from `always25` and the 2026-10-22 deep-research report. The registry now holds 76 trials.
- **Concentration:** two of 182 entries made 54% of the hedged book's round-trip net.
- **Stress model:** Black-Scholes, an instantaneous drop and no vol shock above 60% IV.
- **Margin and fills:** margin is not modelled. Fills of 50-100 contracts in March 2020 use the same spread model as one contract.
- **Spread model:** fitted on two weeks of calm 2026 quotes.
- **Data gaps:** 3.3% of scheduled times are skipped. `hedged` also had 9 unfilled orders and 2 positions that expired after a missed time exit.
- **Accounting:** net P&L reconciles exactly with cash flows. Round-trip sums are about $8.3k lower for `hedged` because share P&L after a stop or expiry is not booked to a round trip.

## Next step
Don't promote yet. The PM decides which rule gets the single look at the 2025-2026 hold-out:
- run this card's hold-out now, on the 35% rule as pre-registered (`/run-experiment-with-report holdout 2026-10-22-stress-sized-puts`);
- or leave this card's hold-out unused and give the one look to a fixed rule from a new card. The report recommends this path.

Possible fixes for the sizing rule's high-vol gap, each in its own card:
- a vol shock relative to current IV;
- a cap on contracts, notional or margin;
- 15% and 25% budgets on the hedged book, as the PM asked. These scale everything down but keep the concentration.

Tiered pricing for share hedges is an IBKR account setting for the PM.
