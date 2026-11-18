# Hypothesis: a bounded deep hedger that prices tail risk beats put20's delta hedge, and the gain is statistically proved on identical trades

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-17-deep-hedger-v2` (config: `configs/experiments/2026-11-17-deep-hedger-v2.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Ben Gorenc (PM) |
| **Status** | failed |
| **Started** | 2026-11-17 |

Designed and run with Claude for Ben. Follows [v1](../2026-11-17-deep-hedger/README.md), which failed: its net learned to under-hedge in selloffs, and its whole lead was March-April 2020. Each change below answers a v1 failure. Code and the pass bar were reviewed by an independent agent before pre-registration; its findings and what was done about each are under Changes.

## Hypothesis
On the live `put20` book, a neural network that sets the hedge each morning **between 0.8× and 1.2× of delta**, trained walk-forward to maximize mean P&L − 0.5 × CVaR95, makes more money than full delta hedging over 2017-2024. The gain must hold in both halves at 1x and 2x spreads, and the **paired per-trade gain on identical simulated out-of-sample trades must have a 95% bootstrap interval above zero**. It may take slightly more risk: Sharpe up to 0.05 lower, ES up to 25% worse, drawdown within the $87,500 stress budget. It must also beat two simpler hedges in the same box: a Hull-White minimum-variance delta and a linear policy.

## Why it matters for the desk
The desk will accept slightly more risk for more return, but only if the return is real. v1 showed a learned hedge can produce a bigger headline P&L out of one lucky crash. v2 asks whether a hedge that stays close to delta, pays for tail risk explicitly and is judged on identical trades adds anything reliable. If it does, it goes to a shadow book. If it doesn't, the desk can stop spending effort on the hedge and look at strikes, sizing and exits instead.

## Data
- **Source:** R2 replay snapshots `data/backtest/v1` at 10:15 ET (decision view; fills from the 15-minute-later fill view), and `features.parquet` (completed days only). Shared panel: `research/Deep_Hedging/lib/panel.py`.
- **Training episodes:** for every trading day from 2014-06-02, three episodes, selling the put the book's rules pick at 15, 20 and 25 delta (Friday expiry nearest 30 DTE in 21-45). Each is sized at **book scale** with the book's own stress rule (`trading.sizing.stress_qty`, 35% budget, 20% drop, 60% IV) and followed daily to the 7-DTE exit with the book's stop and profit-take. Costs follow the engine: the 10-share band, $0.005/share with a $1 minimum per order, $0.005 share half-spread, option fills at the fill-view bid/ask ($0.65/contract, $1 minimum).
- **Walk-forward:** the model for year Y uses only episodes that exited before 1 January Y. Inside that window, the last 20% by entry date is a validation set for early stopping. Models are retrained each January for 2017-2024; before 2017 the book hedges full delta.
- **Backtest window:** development only, 2014-06-02 to 2024-12-31. The hold-out (2025+) is not touched.

## Method
- **Policy:** hedge shares = ratio × the book's delta-hedge shares, ratio = 0.8 + 0.4 × sigmoid(net(x)). It starts at exactly 1.0 (delta).
- **Inputs:** v1's nine plus two new ones. The nine are |delta|, days to expiry/30, the put's IV, VIX, VIX/VIX3M, 20-day realized vol, 5- and 20-day SPY returns, and P&L so far/credit. The new ones are the **current hedge as a share of delta**, for cost awareness (Cao et al. 2021), and **vega/spot**. Engine and training share one input builder (`src/lsgamma/backtest/deep_hedge.py`).
- **Objective (maximized):** mean episode P&L − λ × CVaR95, with λ = 0.5. In words, a dollar of average profit is worth taking only if it adds less than $2 to the average loss of the worst 5% of trades. Exit flags and the band test are not differentiated.
- **Training:** MLP 11→16→16→1 (tanh), 5-seed ensemble (mean ratio), Adam lr 0.003, weight decay 0.001, up to 400 epochs. The validation objective is checked every 20 epochs and the best state is kept. Epoch 0 (pure delta) counts, so the net only moves off delta when validation supports it.
- **Baselines in the same 0.8-1.2 box:**
  - `hw`: Hull-White (2017) minimum-variance delta. Walk-forward OLS of the delta-hedge error on (vega/√T)(ΔS/S)[1, δ, δ²] over all panel puts (`lib/baselines.py`). Agent check before the run: its unclipped ratio for 20-delta puts is about 1.17-1.32, so the 1.2 cap binds in 2017-2022. The box is kept for all policies by design: v1 showed what an unbounded learned hedge does.
  - `linear`: the same training with no hidden layer.
- **Sensitivities (cannot pass this card):** `deep_l025` (λ = 0.25, more return-seeking) and `deep_l1` (λ = 1.0, more risk-averse).
- **Seed check (episodes only, no trials):** the primary model retrained with two other seed sets.
- **Paired test:** every policy is rolled out by the training simulator (not the engine) on the same out-of-sample episodes (20-delta, entered in year Y, model Y), at 1x and 2x costs. The gain is per-trade P&L minus `put20`'s. The 95% interval is a circular moving-block bootstrap over entry months: block 6 months, 10,000 resamples, seed 0 (`lib/evaluate.py`). Block 6 was chosen over 3 because the agent's coverage test on autocorrelated data showed block 3 covering only about 90%.
- **Trials:** 5 variants × 1x and 2x = 10. The `put20` reference is the registered `2026-11-17-deep-hedger/put20` runs, with the same config; it is reused, not rerun.

## Metric and pass bar
`deep` against `put20`, every check at **both 1x and 2x**:

| # | Check | Rule |
|---|---|---|
| 1 | Net P&L, full window | higher |
| 2 | Net P&L, 2017-2020 | higher |
| 3 | Net P&L, 2021-2024 | higher |
| 4 | Paired per-trade gain 2017-2024, bootstrap 95% lower bound | > $0 |
| 5 | Sharpe, 2017-2024 | ≥ `put20` − 0.05 |
| 6 | ES 5% (daily), 2017-2024 | within 1.25× of `put20` |
| 7 | Max drawdown, 2017-2024 | ≤ $87,500 |
| 8 | Net P&L 2017-2024 vs `hw` | higher |
| 9 | Net P&L 2017-2024 vs `linear` | higher |

Floor: ≥ 100 round trips closed in 2017-2024, else inconclusive.

**Reported, not pass checks:** engine gain without 19 Feb-30 Apr 2020; share of years with a positive paired gain; the seed check; each baseline and sensitivity scored against checks 1-7.

## If it passes
Freeze the 2024 model, write `Hedging/deep_hedge.py` (`target_shares`), add a shadow book, and bring it to the PM for one hold-out run. If `deep` fails only checks 8-9 because `hw` or `linear` pass 1-7, the simpler policy is the candidate, and it needs its own confirmatory card, since it was a baseline here. If nothing passes, record that daily delta hedging is close to optimal for put20 and move the topic to simulated-crash training or to exits.

## Disclosures (before the run)
- **The 2017-2024 window is not fresh.** v1 ran on it, and this design (the 0.8-1.2 box, λ, the new inputs, early stopping) was chosen after seeing v1's results. The risk tolerance is looser than v1's (ES 1.25× instead of 1.10×; Sharpe may be 0.05 lower) because the PM asked for a strategy that may take slightly more risk if returns are proved. v1 failed ES at about 1.46×, so v1 would still fail this bar. **v1 and v2 are one family: 6 + 10 = 16 trials.** The confirmatory test is the 2025+ hold-out, run once by the PM, only if this passes.
- **The paired test is simulator-based.** Its episodes start every day and overlap; the engine trades one put at a time. The report shows how well the simulator matches the engine on the 2014-2016 `put20` trades (data the models never score on).
- **Known engine attribution issue, not fixed here:** when a new put takes over the previous put's leftover shares, `engine.carry()` books them at the decision-view spot, while hedge trades fill at the fill-view spot. That shifts a few hundred to a couple of thousand dollars of P&L between trades and can move a stop by a day. Book-level equity is unaffected. It hits every book, `put20` included, and fixing it would change every registered result, so it gets its own fix; here it affects both arms alike.
- **`linear` is effectively one model:** with no hidden layer, a zero-initialized head and full-batch training, its 5 seeds train identically.

## Changes
- 2026-11-17, before pre-registration, after the independent review:
  - **Risk checks 5-7 moved from the full window to 2017-2024.** Before 2017 every variant equals `put20` by construction, which diluted the comparison. The report now asserts that equality.
  - **Engine fix:** on a put's entry day the holding input is 0, as in training. The carried shares from the previous put put it outside the training range (reviewer: median 0.36, up to 2.5).
  - **Training:** a step with no close quote no longer allows a free close.
  - **Checks:** the inference check covers every model kind with mixed path inputs.
  - **Not adopted:** a purge gap between fit and validation. Fit trades all exit before the split date and validation trades all enter on or after it, so they share no price days.
