# Summary: 2026-11-17-deep-hedger

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).
> Written by Claude for Ben Gorenc (PM), who owns the experiment; Ben to review and edit.

**Owner:** Ben Gorenc (PM) · **Date finished:** 2026-11-17 · **Verdict:** failed

## Result
The walk-forward deep hedger (`deep`) made more money than the live `put20` book over the full window, but failed 8 of 14 checks at 1x and 2x spreads. Its Sharpe was lower, its tail and drawdown were much worse, and it lost to `put20` in 2021-2024. Development window 2014-06-02 to 2024-12-31. Models were active from 2017; 2014-2016 is identical to `put20` by design.

| Check (`deep` vs `put20`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $171,595 vs $149,893 | $146,130 vs $133,123 | pass |
| Net P&L, 2017-2020 | $75,082 vs $34,548 | $60,140 vs $27,744 | pass |
| Net P&L, 2021-2024 | $38,519 vs $57,351 | $33,311 vs $52,701 | fail |
| Sharpe, full window | 0.52 vs 0.78 | 0.44 vs 0.69 | fail |
| ES 5% within 1.10× | −$3,591 vs −$2,457 | −$3,670 vs −$2,489 | fail |
| Max drawdown ≤ $87,500 | $96,462 | $104,274 | fail |
| Net P&L 2017-2024 vs `const` | $113,601 vs $92,312 | $93,452 vs $81,376 | pass |
| Round trips 2017-2024 (floor ≥ 100) | 147 | | met |

- **The reference reproduces the registered run exactly:** `put20` here gives $149,893 / Sharpe 0.78 / drawdown $48,435 at 1x, the same as `2026-11-02-lower-delta/put20`. The engine hook changes nothing when it is off.
- **The constant control learned "hedge 100% of delta".** The best constant share was 1.0 in every year except 2017 (0.95), so `const` is essentially `put20` ($150,306 at 1x). Check 7 passed only because `const` is `put20`.

## Trials
- 6 trials: 3 variants (`put20`, `const`, `deep`) × 1x and 2x, from one run of `experiment.py`. Rows are tagged `080e076-dirty`. The pre-registration commit is 080e076; the flag comes from an unrelated untracked card folder (`2026-11-17-put20-partial-hedge/`). Code, config and card did not change.
- One extra, unregistered reproduction run of `put20` at 1x was made before pre-registration, to time the engine and check that it matches Gabe's registered numbers.
- The models were trained once with the pre-registered hyperparameters (policy hashes: const `c43bf5287c80`, deep `e2a1bdce31dd`). Nothing was tuned. The pass bar was not changed.

## What surprised you
- **The net learned to sell more downside exactly when the market is falling.** It hedged about 129% of delta when VIX was below 13, and only about 59% when VIX was above 35 (mean ratio by VIX bucket, `figures/ratio_by_vix.csv`). That is not a hedge; it is a buy-the-dip bet. Training data from 2015-2016 rewarded it, because those sell-offs bounced inside the put's life.
- **The whole lead is March-April 2020.** Between 19 Feb and 30 Apr 2020, `deep` made $33.1k more than `put20`. Over 2017-2024 without that window, it made $11.4k *less*. It is ahead in only 3 of 8 active years (2019, 2020, 2021).
- **The same month is the drawdown.** Under-hedged into the crash, `deep` lost $96k from 4 to 17 March 2020, twice `put20`'s worst drawdown, then got it back in the rebound. That bet happened to pay once; it breaks the stress budget.
- **It traded the tail for profit-takes.** In 2017-2024 it had 35 profit-takes (+$192k) against 25 (+$73k), but 15 stops (−$123k) against 12 (−$61k).
- **The training-side CVaR improvement did not carry over.** On the per-contract episodes the net beat delta's CVaR95 in every training set, but on the following year's episodes it was worse in 5 of 8 years. Classic overfitting on about 100 independent monthly paths.

## Caveats
- **Small sample.** Episodes overlap (one per day, ~20-day life), so the effective sample is roughly one path per month; a few crashes decide everything.
- **The objective allowed speculation.** "Mean, with CVaR95 no worse than delta" lets the net raise the mean by any route that keeps a 5% tail on *training* data, including a long-SPY tilt in sell-offs. The literature warned about this (François et al. 2024; desk report 2026-11-11). This card tested a profit-seeking objective on purpose; a risk-only objective was not tested.
- **Training vs backtest gaps:** training is per contract, has no 10-share band and no $1 minimum per order, and unwinds the hedge at exit (the engine carries orphan shares). Stress sizing does not know the hedge is partial.
- **Data:** spread model fitted on calm 2026 quotes; about 3.3% of scheduled times skipped, as in every R2 run.

## Next step
Archive this card. Two follow-ups are worth their own cards:
1. **Risk-only objective** (minimize CVaR95 or semi-variance of hedged P&L, no mean term), with the hedge share bounded to [0.8, 1.2]. It answers whether there is any *hedging* (not betting) value in the state, as the papers recommend.
2. **Train on simulated paths with crashes** (Heston + jumps fitted pre-2017), then test on R2, so the net sees many more sell-offs than the ~4 in 2014-2016.

The infrastructure built here (`deep_hedge` engine flag, R2 episode panel, walk-forward trainer) can be reused by both.
