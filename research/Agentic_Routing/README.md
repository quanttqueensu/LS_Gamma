# Agentic Routing

**Question for the desk:** given the market state, which structure should we run (or should we stay flat), and can a regime model, an RL policy or an LLM agent choose better than the fixed VRP band rule?

## Who's working on it
| Name | GitHub | Role | Since |
|---|---|---|---|
| TBD | | | |

## Background reading
- Onboarding: Lessons 8 and 10 (`docs/education/`)
- Reports: [Agent routing: which algo to run](../strategy_research/2026-09-27-agent-routing-which-algo-to-run.pdf) · [Signal generation for market state](../strategy_research/2026-09-29-signal-generation-for-market-state.pdf) · [Clustering for algo selection](../strategy_research/2026-10-01-clustering-k-means-for-algo-selection.pdf)
- Papers in `docs/papers/`:
  - `Agents-Are-not-Algorithms.pdf`
  - `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf`
  - `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf` (whitepaper, simulated)
  - `Downside-Risk-Reduction-Using-Regime-Switching-Signals-A-Statistical-Jump-Model-Approach.pdf`
  - `Learning-Hidden-Markov-Models-with-Persistent-States-by-Penalizing-Jumps.pdf`
  - `Harvesting-the-Volatility-Risk-Premium-A-Learning-to-Rank-Approach.pdf`

## Code
Live signals are in `src/lsgamma/signals/` (`SIGNALS` registry). The 10 execution structures are in `src/lsgamma/core/Algos/` (`LG_*`, `SG_*`). Any router must choose only from that menu, and runs in shadow mode before it trades.

## Experiments
| Date | Hypothesis | Owner | Status | Summary |
|---|---|---|---|---|
| 2026-10-07 | [Skipping shorts when VIX curve is inverted raises short precision](2026-10-07-vix-term-gate/README.md) | Gabe Soler (PM) | failed | [summary](2026-10-07-vix-term-gate/summary.md) |
