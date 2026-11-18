# Summary: 2026-11-17-deep-hedger-v2

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).
> Drafted by Claude for Ben Gorenc (PM), who owns the experiment.

**Owner:** Ben Gorenc (PM) · **Date finished:** 2026-11-17 · **Verdict:** failed

Full report: [2026-11-17-deep-hedger-v2.pdf](2026-11-17-deep-hedger-v2.pdf)

## Result
The bounded, risk-priced deep hedger (`deep`, ratio 0.8-1.2× delta, λ = 0.5) did **not** beat `put20`'s plain delta hedge. It made less money, had a lower Sharpe, and on identical out-of-sample trades it was **significantly worse**: the 95% interval of its per-trade gain lies entirely below zero. It passed 9 of 18 checks (1x and 2x). Development window 2014-06-02 to 2024-12-31; models active from 2017; hold-out not touched.

| Check (`deep` vs `put20`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $143,298 vs $149,893 | $126,344 vs $133,123 | fail |
| Net P&L, 2017-2020 | $34,659 vs $34,548 | $27,715 vs $27,744 | pass / fail |
| Net P&L, 2021-2024 | $50,645 vs $57,351 | $45,950 vs $52,701 | fail |
| Paired gain per trade, 95% lower bound > 0 | −$163 [−$299, −$50] | −$166 [−$308, −$48] | fail |
| Sharpe 2017-2024 ≥ put20 − 0.05 | 0.41 vs 0.61 | 0.35 vs 0.53 | fail |
| ES 5% 2017-2024 within 1.25× | −$3,059 vs −$2,705 | −$3,094 vs −$2,740 | pass |
| Max drawdown 2017-2024 ≤ $87,500 | $74,086 | $78,278 | pass |
| P&L 2017-2024 vs `hw` | $85,304 vs $57,461 | $73,665 vs $45,811 | pass |
| P&L 2017-2024 vs `linear` | $85,304 vs $74,460 | $73,665 vs $61,461 | pass |
| Round trips 2017-2024 (floor ≥ 100) | 145 | | met |

Nothing else beat `put20` either. Paired gain per 20-delta trade, 1x, 1,929 out-of-sample trades:

| Policy | Mean gain per trade | 95% interval | Years positive (of 8) | Engine P&L 2017-2024 |
|---|---|---|---|---|
| `deep` (λ 0.5) | −$163 | [−$299, −$50] | 0 | $85.3k |
| `deep_l025` (λ 0.25) | −$98 | [−$183, −$20] | 1 | $86.3k |
| `deep_l1` (λ 1.0) | −$95 | [−$170, −$25] | 0 | $87.8k |
| `deep`, seed set 2 / 3 | −$122 / −$129 | both below 0 | 0 / 0 | not run |
| `linear` | −$58 | [−$180, +$54] | 1 | $74.5k |
| `hw` (Hull-White, capped at 1.2) | −$110 | [−$293, +$81] | 2 | $57.5k |
| `put20` (delta) | 0 | | | $91.9k |

## Trials
- **10 trials:** 5 variants × 1x and 2x, one run of `experiment.py`, all tagged `21ea61c` (clean tree). The `put20` reference is the registered `2026-11-17-deep-hedger/put20` runs, reused. The report asserts every variant equals it before 2017.
- **Family total with v1: 16 trials.** The seed checks were scored on episodes only and add no trials. The pass bar was changed once before pre-registration, after the independent review (see the card's Changes); not after.

## What surprised you
- **The negative result is statistically solid, unlike v1's positive one.** Every learned variant and both extra seed sets lose $95-163 per trade, with intervals that exclude zero. `deep` and both seed sets lose in every year except 2018, when early stopping chose pure delta and they matched it exactly. The sensitivities are similar: `deep_l025` gained only in 2019 (+$15 per trade) and `deep_l1` never gained. Seed sets 2 and 3 agree within about $40 per trade.
- **The net still leans the v1 way, just less.** It hedged about 1.12× delta with VIX under 13 and about 0.93× above 35, a mild version of v1's buy-the-dip tilt. The linear policy did the same: 0.84× above VIX 35.
- **Early stopping helped, but not enough.** Validation picked pure delta in 2018 for every variant. In other years it found a deviation that looked better on the last 20% of the training window and then lost the next year. The validation window (about a year) is too short and too noisy to pick a winner.
- **The one real effect is Hull-White's "hedge more".** Hedging about 1.2× delta, the leverage-effect hedge, cut paired CVaR95 from $8,590 to $7,040 per trade (−18%) and the engine's 2017-2024 drawdown from $48k to $41k. It cost $34k of P&L (Sharpe 0.40 vs 0.61). That is a risk dial, not a return source.
- **A bounded hedge still widened the drawdown.** It reached $74k vs $48k, at the same 16 March 2020 trough, from being about 7% under-hedged into the crash and from different stop timing.
- **The simulator tracks the engine well.** On the 48 pre-2017 `put20` trades: 48 of 48 matched, correlation 0.92, totals $59.0k vs $57.1k. The paired test measures the right thing.

## Caveats
- **The window was seen before:** 2017-2024 had already been used by v1 (disclosed on the card). That would bias toward a false pass, not a fail.
- **The paired test runs in the simulator, not the engine,** on overlapping daily episodes. The engine results agree in direction.
- **Engine carry attribution:** leftover shares are booked at the decision spot, not the fill spot (card, Disclosures). It hits both arms and is not fixed here.
- **Training gaps:** stress sizing still assumes a full hedge. The model switches on 1 January even mid-trade.

## Next step
Archive. Two attempts (16 trials) agree that for put20, a learned daily hedge ratio does not add return over plain delta hedging. Within ±20% it costs about $100-160 per trade out of sample; unbounded (v1), it turned into a crash bet. Recommendations:
1. **Stop pursuing the hedge as a return source** for this book.
2. **If the desk wants a smaller tail,** write a card for a fixed over-hedge (e.g. 1.1-1.2× delta, or Hull-White) as an explicit risk-for-return trade, judged on drawdown and CVaR per dollar of P&L given up.
3. **Fix the engine's carry attribution** (`engine.carry()` should price at the fill spot) on its own branch. It changes every registered result, so the PM should decide.
4. **Look elsewhere for return:** exit rules (stop and profit-take), strike and sizing, where the earlier experiments show the path effects really sit.
