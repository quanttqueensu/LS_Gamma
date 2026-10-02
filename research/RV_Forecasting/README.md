# RV Forecasting

**Question for the desk:** can we forecast SPY's realized volatility over the life of a trade better than the live GARCH model? The forecast drives the VRP signal (`vrp = iv - rv_forecast`), so a better forecast means better trades.

## Who's working on it
| Name | GitHub | Role | Since |
|---|---|---|---|
| TBD | | | |

## Background reading
- Onboarding: Lesson 7 (`docs/education/Lesson-07-Forecasting-Volatility.pdf`)
- Reports: [ML/RL for realised volatility forecasting](../strategy_research/2026-09-27-ml-rl-for-realised-volatility-forecasting.pdf) · [Leverage effect and the desk](../strategy_research/2026-09-27-leverage-effect-and-the-ls-gamma-desk.pdf) · [Walk-forward backtesting](../strategy_research/2026-10-01-walk-forward-backtest-without-look-ahead.pdf)
- Papers in `docs/papers/`:
  - `A-machine-learning-approach-to-volatility-forecasting.pdf`
  - `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`
  - `Realised-Volatility-Forecasting-Machine-Learning-via-Financial-Word-Embedding.pdf`
  - `Foundation-Time-Series-AI-Model-for-Realized-Volatility-Forecasting.pdf`
  - `Improving-S&P-500-Volatility-Forecasting-through-Regime-Switching-Methods.pdf`
  - `Time-Series-Embedding-and-Combination-of-Forecasts-A-Reinforcement-Learning-Approach.pdf`

## Code
Live forecasters are in `src/lsgamma/forecasting/` (`GARCH.py`, `HAR.py`, `FORECASTERS` registry). A new model must implement `fit(returns)`, `predict(horizon)` and `params()`.

## Experiments
| Date | Hypothesis | Owner | Status | Summary |
|---|---|---|---|---|
| 2026-10-05 | [HAR beats GARCH on 20-day RV](2026-10-05-har-vs-garch/README.md) (worked example) | TBD | running | [summary](2026-10-05-har-vs-garch/summary.md) |
