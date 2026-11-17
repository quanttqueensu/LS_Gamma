# Hypothesis: a deep hedger trained walk-forward on R2 makes the live put20 book more money than full delta hedging, without a worse tail

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-17-deep-hedger` (config: `configs/experiments/2026-11-17-deep-hedger.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Ben Gorenc (PM) |
| **Status** | planned |
| **Started** | 2026-11-17 |

Designed and run with Claude for Ben. Pre-registered by committing this card, the config and the code before any walk-forward model was scored.

## Hypothesis
On the live `put20` book (always-short 20-delta SPY put, 35% stress budget, 10-share band, hedged daily at 10:15), letting a small neural network choose **what share of the put's delta to hedge each morning** (0 to 150%) raises net P&L over 2017-2024 versus hedging 100% of delta. It does so in both halves of that window, at 1x and 2x spreads, with ES 5% no more than 10% worse and max drawdown within the $87,500 stress budget. It also beats the best **constant** hedge share trained the same way, so the gain comes from reacting to the state and not from a fixed beta tilt.

## Why it matters for the desk
Every hand-built hedge change so far (VRP unhedge, VRP partial hedge, minimum-variance) failed. Each was a single rule picked by hand. This tests the deep-hedging claim that a policy trained to a risk objective after costs can find a better state-dependent rule than delta. If it passes, it is the first candidate for `Hedging/deep_hedge.py` and a shadow book. If it only matches the constant ratio, the desk learns that the edge (if any) is a beta choice, not "smart" hedging.

## Data
- **Source:** R2 replay snapshots `data/backtest/v1`, 10:15 ET decision and fill views; `features.parquet` for VIX, VIX/VIX3M and SPY returns (completed days only).
- **Training episodes:** one per trading day from 2014-06-02. Each episode sells the put the book would sell that morning (Friday expiry nearest 30 DTE within 21-45, strike nearest 20 delta), fills at the fill-view bid, then follows that contract daily at 10:15. It applies the book's stop (loss ≥ 1× credit) and profit-take (≥ 50% of credit) on option + hedge P&L, and closes at the 7-DTE time exit at the fill-view ask. Costs are $0.005/share commission + $0.005 half-spread on shares and $0.65 per contract each way. Per contract, 1x costs.
- **Walk-forward:** the model for year Y is trained only on episodes whose exit is before 1 January Y. It is retrained each January for 2017-2024, so the first model sees 2014-06 to 2016-12. Before 2017 the book hedges 100% of delta, which makes 2014-2016 identical to `put20`.
- **Backtest window:** development only, 2014-06-02 to 2024-12-31 (`configs/backtest.toml`). The hold-out (2025-01-01+) is not touched.

## Method
- **Policy:** hedge shares = ratio × the book's delta-hedge shares, ratio = 1.5 × sigmoid(MLP(x)). Nine inputs: the put's |delta|, days to expiry/30, the put's IV, VIX, VIX/VIX3M, 20-day realized vol, 5- and 20-day SPY return, and the position's P&L so far over its credit. MLP 9→16→16→1, tanh. The output layer starts at zero, so an untrained net is exactly delta hedging. Ensemble of 5 seeds (ratios averaged). Adam, lr 0.003, 300 full-batch epochs, weight decay 0.001. Fixed in the config; not tuned.
- **Objective (training):** maximize mean episode P&L − 10 × max(0, CVaR95(policy) − CVaR95(delta hedge)), where CVaR95 is the mean loss of the worst 5% of training episodes. In words: make as much as possible without a worse tail than delta hedging. Gradients pass through the share holdings; stop and profit-take flags are not differentiated.
- **Control `const`:** one hedge share per year, from {0, 0.05, …, 1.5}, chosen with the same objective on the same episodes.
- **Into the backtest:** a research-only flag `deep_hedge` in `configs/backtest.toml` (default off) points `engine.target()` at the yearly models; the 10-share band, sizing, exits and costs are unchanged. Engine code: `src/lsgamma/backtest/deep_hedge.py`.
- **Variants:** `put20` (reference, rerun here: ratio 1), `const`, `deep` (primary). 3 variants × 1x and 2x = 6 trials.

## Metric and pass bar
`deep` against `put20`, every check at **both 1x and 2x**:

| # | Check | Rule |
|---|---|---|
| 1 | Net P&L, full window 2014-06 to 2024-12 | higher |
| 2 | Net P&L, 2017-2020 | higher |
| 3 | Net P&L, 2021-2024 | higher |
| 4 | Sharpe, full window | higher |
| 5 | ES 5% (daily), full window | within 1.10× of `put20` |
| 6 | Max drawdown, full window | ≤ $87,500 (35% stress budget) |
| 7 | Net P&L 2017-2024, `deep` vs `const` | higher |

Floor: ≥ 100 round trips closed in 2017-2024, else inconclusive.

## If it passes
Write the clean `Hedging/deep_hedge.py` (`target_shares`) with a frozen model, add it as a shadow book, and bring it to the PM for a hold-out decision. If `const` beats `put20` but `deep` doesn't beat `const`, the result is a beta tilt, and the follow-up is a card on the hedge share alone. If neither beats `put20`, archive the card.

## Changes
None.
