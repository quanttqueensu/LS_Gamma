# Summary: 2026-11-05-ltr-puts

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-11-05 · **Verdict:** failed

Full report: [2026-11-05-ltr-puts.pdf](2026-11-05-ltr-puts.pdf)

## Result
The test put a LightGBM LambdaRank ranker, built as in Wysocki (2026), on the 35% stress-sized `hedged` put book. Each day from 2017 it picked the put delta (0.05-0.45) or no trade, retrained yearly. It failed: Sharpe was lower in 2014-2019 at both spreads.

The primary is `ltr` (top pick, SKIP and the paper's confidence gate); the reference is the registered `2026-10-22-stress-sized-puts/hedged`; the window is 2014-06-02 to 2024-12-31.

| Check (`ltr` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Sharpe, full window | 0.84 vs 0.52 | 0.67 vs 0.43 | pass |
| Sharpe, 2014-06 to 2019-12 | 0.64 vs 0.84 | 0.43 vs 0.72 | fail |
| Sharpe, 2020-01 to 2024-12 | 1.09 vs 0.48 | 0.95 vs 0.38 | pass |
| Max drawdown ≤ $87,500 | $14,810 | $19,835 | pass |
| ES 5% within 1.10x | −$1,546 vs −$3,016 | −$1,566 vs −$3,094 | pass |
| Round trips (floor ≥ 30) | 165 | | met |

The book makes less money: $80,124 at 1x and $63,822 at 2x, against $121,482 and $101,172. All books are identical until 2017-01-09.

Sensitivities (reported only):
- `ltr_nogate` and `ltr_noskip` are identical runs. The ranker put SKIP first on 1 of 1,944 test days, while the book held a put.
- Strike choice only: $112,100 / $105,115; Sharpe 0.55 / 0.51; max drawdown $52,803 / $52,488. It fails the same 2014-2019 check (0.53 vs 0.84 at 1x).

## Trials
- 6 trials (3 variants × 1x and 2x, one run), all tagged with the pre-registration commit 7964782. The `hedged` reference and the baseline were reused, not rerun.
- The labels came from 21,320 unregistered engine runs (20,376 labels); they are training data, not trials.
- Two earlier starts were stopped while building labels, before any trial or label existed:
  - another process switched the shared working tree to `main`;
  - thread oversubscription.
- One chart was fixed afterwards with `--report-only`.
- The pass bar was not changed.

## What surprised you
- **The gate, not the ranking, made the result.**
  - SKIP won the ranking only once, on a day the book already held a put, so `ltr` skipped only when the top-two score gap was below τ (603 entry days).
  - τ was set on each window's last half-year, and the share of days the book would trade swung from 7% to 100% between adjacent years.
  - 2020's τ, set on late 2019, abstained on all 49 days from 19 February to 30 April 2020. The book was in the market on 6% of those days (−$151), against +$21.7k for the reference, whose $70.4k maximum drawdown bottomed in that window.
  - Outside that window, Sharpe was 0.85 against 0.81 at 1x (0.68 against 0.66 at 2x).
- **The ranker loves 5- and 10-delta puts** (37% and 28% of test days). The paper's path score rewards their quick profit-takes, but 5-delta puts earn the least of all eight.
  - 5-delta labels averaged $35 against $607 for 25-delta.
  - From 2017, `ltr`'s 57 entries at 5-delta made $4.4k in total.
- **It has some skill on its own target, but not in money.** In the walk-forward test years, its pick was the day's best-scoring put 25% of the time (12.5% by chance, 6% for 25-delta). But the label-level P&L edge over 25-delta, $69 a day, is not reliable (t = 0.57 on monthly means).
- **The models stayed tiny:** early stopping on about 42 days of NDCG@1 gave 3-45 boosting rounds per window.

## Caveats
- **In-sample design:** the book was chosen after its 2014-2024 results, and the desk had seen results by delta before this card. The walk-forward protects only the yearly picks.
- **One episode:** most of the Sharpe and drawdown gap is the 2020 crash window.
- **Departures from the paper:**
  - 30-DTE SPY puts held to the book's exits, not 0DTE SPXW held to settlement;
  - daily bars;
  - net P&L in the label;
  - fixed hyperparameters and features (no Optuna search, no S1-S5 selection);
  - no put-call ratios.
- **Fills:** far out-of-the-money puts often have no fill price near expiry, so closes fail and the put is held to settlement. There were 52 failed close attempts on 10 `ltr` puts (9 expired), against 9 on 2 reference puts.
- **Model limits:** the spread model was fitted on calm 2026 quotes; margin is not modelled; about 3.3% of scheduled times are skipped.

## Next step
Archive this card, and don't run the out-of-sample test. If the gate is worth pursuing, it needs its own card: a gate judged on several selloffs (August 2015, February 2018, Q4 2018), designed without looking at 2020. A P&L-based label is the other open variant.
