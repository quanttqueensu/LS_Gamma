# Hypothesis: on the stress-sized put book, a learning-to-rank model that picks each day's put delta, or no trade, beats the fixed 25-delta put on Sharpe

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-05-ltr-puts` (config: `configs/experiments/2026-11-05-ltr-puts.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (Sharpe lower in 2014-2019; full-window Sharpe 0.84 vs 0.52 but P&L $80k vs $121k, mostly from a gate that sat out 2020) |
| **Started** | 2026-11-05 |

## Hypothesis
On the 35% stress-sized `hedged` put book, a LightGBM LambdaRank ranker built as in Wysocki (2026) gives a higher Sharpe ratio than the fixed 25-delta book at 1x and 2x spreads, over the full window and in each half. The ranker is trained walk-forward from 2017 and each day picks the put delta to sell (0.05 to 0.45) or no trade. The book must stay within the $87,500 drawdown budget, with a 5% expected shortfall no more than 1.10 times worse.

## Why it matters for the desk
The paper (`docs/papers/Harvesting-the-Volatility-Risk-Premium-A-Learning-to-Rank-Approach.pdf`) describes exactly the desk's book as the passive harvester it tries to beat:
> "the position is held continuously regardless of the prevailing market regime, so capital is allocated identically on days when the per-trade premium is wide and on days when it is narrow" (p. 2)

Its ranker scores eight delta-targeted short puts and a SKIP option each day and trades the top one. Out of time it reports Sharpe ratios of 4.3-5.8 on 0DTE SPXW, but the paper notes these rest on one year.

The desk's own tests split the same decision into single rules, and none of them was robust:
- **Strike:** 20-delta passed in-sample, but $26.5k of its $28.4k lead is August 2015.
- **Timing:** VRP, VIX-curve and VVIX gates and tilts all failed.
- **Skew vs delta:** the diagnostic found nothing card-worthy.

A ranker can use these inputs together, through interactions. If it works, it is the desk's first learned routing rule: it chooses among put structures instead of following one fixed rule.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the walk-forward keeps each year's picks out of its own training, but the design is not blind.
  - The book is the 2026-10-22 primary, chosen after its 2014-2024 results.
  - The desk has seen 2014-2024 results for 15-, 20-, 25-, 35-delta and ATM puts, and forward P&L by delta bucket (2026-11-02 skew diagnostic).
  - The paper was flagged in the 2026-10-31 signals report.
  - Before pre-registration, Claude:
    - checked that the engine with the new switch off reproduces the baseline and `hedged` equity exactly;
    - smoke-tested the label and feature code on 5 days of June 2014 (structure and timing only; P&L not examined);
    - tested the ranker, gate and picks on synthetic random labels.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop, with IV at max(60%, the put's IV), stays within 35% of capital ($87,500).
  - Hedged daily with a 10-share band.
  - The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482, Sharpe 0.52 at 1x; +$101,172, Sharpe 0.43 at 2x), reused and not rerun.
- **New switch:** `[backtest] put_picks` (default off). It names a file of daily picks in `results/research/`.
  - On a day with a pick, the short put's delta target is that pick, and 0 means no entry that day (event `pick_skip`).
  - On days without a pick, the book uses `put_delta` (0.25).
  - Long calls are untouched.
  - 4 tests.
- **Candidates (paper eq. 1):** each day, 8 short puts at |delta| 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40 and 0.45, plus SKIP.
  - Each put is on the book's expiry (the Friday closest to 30 DTE within 21-45 DTE) and stress-sized as the book would size it.
- **Labels:** for every development day and each delta, one engine run opens that put at 10:15 and holds it under the book's rules until it first closes. These runs are unregistered; they are the training data, not trials.
  - Runs use 1x spreads; about 21,000 runs, built once inside `experiment.py`.
  - The score follows paper eq. 6: net round-trip P&L / (√Σ min(Δmarkᵢ, 0)² + 10⁻⁸), over the daily 10:15 marks of the position and its hedge.
  - SKIP scores 0.
  - Grades 0-4 come from the 10th/40th/60th/90th percentiles of non-SKIP scores in each window's fit set (eq. 7-8).
- **Features (fixed list of 37):**
  - **Prior close:** VIX, VIX 1-year percentile, VIX/VIX3M, VIX9D/VIX, VVIX, RV (daily, weekly, monthly), above the 50- and 200-day averages, last return, 5- and 20-day returns, 5-day VIX change.
  - **10:15 chain:** ATM IV, GARCH forecast, VRP, DTE, term slope (ATM IV minus the nearest expiry of 5+ DTE), 25-delta skew, 10-25-delta wing.
  - **Calendar:** weekday, days to the next scheduled FOMC statement and CPI release (official dates, 2014-2024).
  - **Per candidate:** target and actual delta, IV, IV minus ATM IV, log-moneyness, premium/spot, relative bid-ask spread, stress-sized contracts; credit, vega, theta and dollar gamma per dollar of stress budget; SKIP flag.
- **Ranker:** LightGBM 4.7.0 `LGBMRanker`, `lambdarank` objective, `label_gain = [0,1,3,7,15]`, one query group per day.
  - Fixed hyperparameters, chosen inside the paper's search ranges before any run: 16 leaves, learning rate 0.05, 100 minimum samples per leaf, row and column subsampling 0.8, L1 0.1 and L2 1.0.
  - Up to 2000 rounds, early stopping on NDCG@1 with patience 50.
  - Single thread, deterministic, seed 0.
- **Walk-forward:** expanding, retrained each year; test years 2017-2024 (8 windows). For test year Y:
  - the ranker fits on days before Y − 9 months;
  - early stopping uses Y − 9 to Y − 6 months;
  - the gate is calibrated on the last 6 months before Y.

  Each slice keeps only days whose labels closed before the next slice starts, so no label overlaps it. The first fit set is 2014-06 to 2016-03.
- **Gate (paper 3.5):** τ is chosen from {0, the 10th-90th percentiles of the calibration slice's top-1/top-2 score gaps}.
  - The chosen τ maximises the Sortino ratio of the slice's top-1 net P&L, counting abstained or SKIP days as 0.
  - The book abstains when the gap is below τ.
- **Variants** (one model per window; three ways to act on it):
  - `ltr` (primary): trade the top pick unless it is SKIP or the gate abstains;
  - `ltr_nogate` (sensitivity): trade the top pick, SKIP included, with no gate;
  - `ltr_noskip` (sensitivity): sell the best-ranked put every day (strike choice only).
- **Fallback:** before 2017, and on any test day without a pick (no usable 10:15 snapshot), every variant sells the 25-delta put. The book is therefore identical to the reference until the first 2017 entry.
- **Runs:** each variant at 1x and 2x spreads, with picks trained on 1x labels used for both.
  - Costs: $0.65 per contract and $0.005 per share with a $1 minimum per order.
  - Schedule: decisions and hedges once a day at 10:15 ET.
- **Trials:** 3 variants × 2 multiples = 6. The label runs are not trials.
- **Deviations from the paper:**
  - 30-DTE puts held to the book's exits, not 0DTE puts held to settlement; daily bars, not 1-minute; net P&L at mid-based marks, not gross at ask marks.
  - SPY, not SPXW.
  - No 50-trial Optuna search: hyperparameters are fixed.
  - No S1-S5 feature-selection pipeline: the feature list is fixed.
  - No put-call ratios or intraday features.
  - Stress-budget sizing, not the paper's seven sizing methods.
  - LightGBM is built without OpenMP and runs single-threaded.
  - Consecutive days' labels share most of their path, so the ~2,600 labelled days hold far fewer independent outcomes than the paper's same-day trades.
- **Also reported, not part of the bar:**
  - each window's fit days, rounds, τ and trade rates;
  - the mix of picks by year;
  - mean label P&L per test day of each variant's pick against the fixed 25-delta pick;
  - feature gain shares;
  - executed entries and net P&L by picked delta.

## Metric and pass bar
Primary `ltr` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Sharpe is higher over the full window.
2. Sharpe is higher in 2014-06 to 2019-12. The book matches the reference until 2017, so this half is decided by 2017-2019.
3. Sharpe is higher in 2020-01 to 2024-12.
4. The maximum drawdown is at most $87,500, the 35% stress budget.
5. **Tail guard:** the 5% expected shortfall of daily P&L is no worse than 1.10 × the reference's.

There is no P&L check: the PM chose a Sharpe bar because the ranker may skip days and trade less.

**Event floor:** `ltr` must have at least 30 round trips at 1x; otherwise the result is INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks):
- One more window is trained on all development labels: fit before 2024-04, early stopping 2024-04 to 2024-06, gate 2024-07 to 2024-12. It picks for 2025-01-01 to 2026-07-10.
- `ltr` is judged against the `hedged` hold-out run, at 1x and 2x, on these checks:
  - Sharpe higher;
  - maximum drawdown at most $87,500;
  - ES within 1.10x.
- Before that run, the 2025-26 FOMC and CPI dates must be added from the official calendars as a dated Changes note.

## If it passes
1. Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`.
2. If it holds, shadow mode: live 10:15 features, the ranker's pick logged daily, no orders.
3. Then a decision record, and live changes reviewed by the PM. Live needs a delta target in `selection.pick_strike` and a picks feed.

## Setup
`lightgbm==4.7.0` is added to `pyproject.toml`. On macOS it needs libomp (`brew install libomp`). Without Homebrew, build it without OpenMP:
`pip install lightgbm==4.7.0 --no-binary lightgbm --config-settings=cmake.define.USE_OPENMP=OFF`. The ranker runs single-threaded either way.

## Changes
- 2026-11-05: the run was started three times; only the third registered trials.
  - **First:** stopped while building labels. Another process switched the shared working tree to `main`, which removed this card's config.
  - **Second:** stopped by Claude while building labels, because 12 workers each started a 14-thread pool and oversubscribed the machine.
  - **Third:** ran from a separate checkout of this branch (commit 7964782, clean) with one thread per worker (`OMP_NUM_THREADS=1` and the BLAS equivalents; no code change).

  Neither of the first two produced labels or trials. The third registered 6 trials, all tagged 7964782.
- 2026-11-05: after the trials registered, the picks chart crashed on a duplicate index. `picks_mix` in `experiment.py` now resets the index (chart code only). The report was rebuilt with `--report-only`, which adds no trials.
- 2026-11-05 result: **failed** at 1x and 2x on the 2014-2019 Sharpe check.
  - `ltr`: Sharpe 0.64 vs 0.84 (1x) and 0.43 vs 0.72 (2x) in 2014-2019; full window 0.84 vs 0.52 and 0.67 vs 0.43.
  - Max drawdown $14,810 / $19,835; ES −$1,546 / −$1,566; net P&L $80,124 / $63,822 against $121,482 / $101,172.
  - 165 round trips.
  - `ltr_nogate` and `ltr_noskip` came out identical: SKIP ranked first on only 1 test day.
  - The pass bar above was not changed. See `summary.md` and `2026-11-05-ltr-puts.pdf`.
