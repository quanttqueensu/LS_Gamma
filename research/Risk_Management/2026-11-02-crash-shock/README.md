# Hypothesis: stressing the put book at max(60%, 1.5x IV) beats the 60% floor on Sharpe and drawdown

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-02-crash-shock` (config: `configs/experiments/2026-11-02-crash-shock.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM) |
| **Status** | failed (Sharpe 0.51 vs 0.52 at 1x, 0.40 vs 0.43 at 2x; drawdown $60k vs $70k) |
| **Started** | 2026-11-02 |

## Hypothesis
On the 35% stress-sized `hedged` put book, sizing each entry for a one-day 20% SPY drop with IV at max(60%, 1.5 × the put's IV), instead of max(60%, the put's IV), gives a higher Sharpe ratio over the full window and in each half, and a less severe maximum drawdown, at 1x and 2x spreads.

## Why it matters for the desk
The stress rule sizes up into high IV: a higher-IV put has a higher premium, so the same crash loss buys more contracts. In 2026-10-22, two March 2020 entries (100 and 71 contracts, IV above 45%) made 54% of the `hedged` book's round-trip net. The stress test never assumes IV rises above 60%, so on those days it understates the loss from a second crash. A shock that scales with IV binds only when IV is above 40%, so it cuts the crash-time size and leaves calm days alone. This was the recommended sizing fix before the 2026-10-22 hold-out look. The 25% and 15% budgets the PM asked for on 2026-10-22 run as sensitivities.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** The idea comes from the 2026-10-22 results on this same window (concentration in high-IV March 2020 entries), and the book is that card's primary, chosen after its results. Only the hold-out can confirm it. Before pre-registration, the desk tested this card's reporting code on the registered `hedged` reference runs only, and so saw that the reference has 4 round trips (of 182) entered with put IV above 40%. No P&L by IV bucket was looked at. This card's variants have no runs yet.

## Method
- **Book (every variant and the reference):** the `hedged` book of `Risk_Management/2026-10-22-stress-sized-puts`.
  - An always-on short 25-delta put, with the signal ignored (`short_band = long_band = -inf`) and the flat exit off.
  - Sized at each entry to the most contracts whose loss in a one-day 20% SPY drop stays within the budget (35% of $250k = $87,500), counting the hedge gain and the 10-share band gap.
  - Hedged daily at 10:15 with a 10-share band. The 1x-credit stop, 50% profit-take, 7-DTE time exit and 1-day cool-off stay as live.
- **Reference:** the registered `2026-10-22-stress-sized-puts/hedged` runs (+$121,482 at 1x, +$101,172 at 2x; Sharpe 0.52 / 0.43; max drawdown $70,362 / $75,488), reused and not rerun. With the new switches off, the engine reproduces its equity exactly (checked before pre-registration, commit a2d5334).
- **New research switch** `[backtest] stress_vol_mult` (default 0 = off): the stress IV is max(`stress_vol`, `stress_vol_mult` × the put's IV). IV is the put's IV in the 10:15 decision chain.
- **Variants:**
  - `shock15` (primary): `stress_vol_mult = 1.5`, budget 35%.
  - `budget25` (sensitivity): budget 25%, today's shock (max(60%, IV)).
  - `budget15` (sensitivity): budget 15%, today's shock.
- **Runs:** each variant at 1x and 2x spreads; $0.65 per contract and $0.005 per share with a $1 minimum per order (IBKR Pro Fixed); decisions and hedges once a day at 10:15 ET.
- **Also reported, not part of the bar:** contracts per entry by year; contracts and P&L by entry-IV bucket; contracts and net P&L of round trips opened 15 February to 30 April 2020.
- **Trials:** 3 variants × 2 multiples = 6.

## Metric and pass bar
Primary `shock15` against reference `hedged` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. The Sharpe ratio is higher over the full window;
2. The Sharpe ratio is higher in 2014-06 to 2019-12;
3. The Sharpe ratio is higher in 2020-01 to 2024-12;
4. The maximum drawdown is less severe (smaller in absolute size).

Raw P&L is not on the bar: a smaller crash-time size makes less money by construction, so the test is whether it makes more per unit of risk.

**Event floor:** `shock15` must have at least 3 round trips at 1x entered with put IV above 40% (where 1.5 × IV exceeds the 60% floor and the new shock binds); otherwise INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `shock15` against `hedged`, both over 2025-01-01 to 2026-07-10, at 1x and 2x, on the full-window checks above (Sharpe higher, maximum drawdown less severe). This needs a hold-out run of the 2026-10-22 `hedged` book, which is also that card's single hold-out look, so the PM decides both together.

## If it passes
Run the hold-out once, together with the PM's hold-out decision for `2026-10-22-stress-sized-puts`. If it holds: shadow mode, a decision record, then live changes reviewed by the PM. Live needs the stress sizing (with the IV multiple) in the runner.

## Changes
- 2026-11-02: run once (6 trials). The pass bar above was not changed. Verdict: failed at 1x and 2x. `shock15` made +$92,985 / +$73,349 against +$121,482 / +$101,172, with Sharpe 0.51 / 0.40 against 0.52 / 0.43 and a 2020-2024 Sharpe of 0.39 / 0.27 against 0.48 / 0.38. Its maximum drawdown was smaller ($60,228 / $65,032 against $70,362 / $75,488). The shock never binds before 2020 (no entry had IV above 40%), so the 2014-2019 Sharpe check could only tie; this flaw in the bar does not decide the verdict. Only 4 entries changed size, all in March-April 2020. All six registry rows are tagged `-dirty` (commits 79b09a1 and 3568520, both containing af47198): other cards in the batch were pre-registered during the run and their uncommitted files were in the shared tree. Engine, `backtest.toml` and this card's files were unchanged. See `2026-11-02-crash-shock.pdf`.
- 2026-11-02 (after the run): chart-only fixes in `experiment.py`. The drawdown legend moved to the lower left, and the March 2020 chart was widened with a shorter right-hand title. Figures rebuilt with `--report-only`; no new trials.
