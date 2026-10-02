# Deep Hedging

**Question for the desk:** can a hedging policy learned with reinforcement learning beat the live daily delta hedge on scalping P&L after costs, without drifting into directional bets?

## Who's working on it
| Name | GitHub | Role | Since |
|---|---|---|---|
| TBD | | | |

## Background reading
- Onboarding: Lessons 5 and 10 (`docs/education/`)
- Reports: [Deep hedging as the gamma scalping P&L driver](../strategy_research/2026-09-27-deep-hedging-as-gamma-scalping-pnl-driver.pdf) · [Leverage effect and the desk](../strategy_research/2026-09-27-leverage-effect-and-the-ls-gamma-desk.pdf)
- Papers in `docs/papers/`:
  - `Deep-Hedging.pdf` (the original framework)
  - `Deep-Hedging-of-Derivatives-Using-Reinforcement-Learning.pdf`
  - `Deep-Hedging-with-Options-Using-the-Implied-Volatility-Surface.pdf`
  - `Application-of-Deep-Reinforcement-Learning-to-At-the-Money-S&P-500-Options-Hedging.pdf`
  - `Is-the-Difference-between-Deep-Hedging-and-Delta-Hedging-a-Statistical-Arbitrage?.pdf`
  - `Hedging-with-Linear-Regressions-and-Neural-Networks.pdf` (the simple baseline to beat)
  - `When-You-Hedge-Discretely-Optimization-of-Sharpe-Ratio-for-Delta-Hedging-Strategy-under-Discrete-Hedging-and-Transaction-Costs.pdf`

## Code
Live hedgers are in `src/lsgamma/core/Algos/Hedging/`. A new hedger exposes `target_shares(ib)`, and `portfolio.rebalance()` trades the difference. The baseline is `delta_hedge.py`.

## Experiments
| Date | Hypothesis | Owner | Status | Summary |
|---|---|---|---|---|
| | | | | |
