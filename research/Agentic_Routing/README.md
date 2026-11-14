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
| 2026-10-07 | [VIX term gate cuts the worst short outcomes (2006–2015 test)](2026-10-07-vix-gate-tail/README.md) | Gabe Soler (PM) | failed | [summary](2026-10-07-vix-gate-tail/summary.md) |
| 2026-10-16 | [Turning long gamma off improves net P&L (option backtest)](2026-10-16-short-only/README.md) | Gabe Soler (PM) | passed (in-sample; hold-out not run) | [summary](2026-10-16-short-only/summary.md) · [report](2026-10-16-short-only/2026-10-16-short-only.pdf) |
| 2026-10-16 | [On the short-only book, a +4 vol-point short band raises net P&L](2026-10-16-short-band-4/README.md) | Gabe Soler (PM) | failed | [summary](2026-10-16-short-band-4/summary.md) · [report](2026-10-16-short-band-4/2026-10-16-short-band-4.pdf) |
| 2026-10-16 | [On the short-only book, a VIX/VIX3M ≥ 1 entry gate cuts the daily tail 20%](2026-10-16-vix-gate-backtest/README.md) | Gabe Soler (PM) | failed | [summary](2026-10-16-vix-gate-backtest/summary.md) · [report](2026-10-16-vix-gate-backtest/2026-10-16-vix-gate-backtest.pdf) |
| 2026-10-17 | [Selling 25-delta puts instead of ATM puts raises net P&L on the best book](2026-10-17-otm-put/README.md) | Gabe Soler (PM) | failed (1 of 8 checks; +$180 at 1x) | [summary](2026-10-17-otm-put/summary.md) · [report](2026-10-17-otm-put/2026-10-17-otm-put.pdf) |
| 2026-10-17 | [Always being short a 25-delta put beats signal-timed shorts](2026-10-17-always-short/README.md) | Gabe Soler (PM) | failed (tail guard; +$1,316 / +$862) | [summary](2026-10-17-always-short/summary.md) · [report](2026-10-17-always-short/2026-10-17-always-short.pdf) |
| 2026-10-21 | [Running the signal every hour instead of once at 10:15 makes more entries](2026-10-21-signal-times/README.md) | Gabe Soler (PM) | passed (entries only: 225 vs 131; net P&L worse) | [summary](2026-10-21-signal-times/summary.md) · [report](2026-10-21-signal-times/2026-10-21-signal-times.pdf) |
| 2026-11-02 | [On the stress-sized put book, opening new puts only on Fridays beats opening them on any day](2026-11-02-friday-entry/README.md) | Gabe Soler (PM) | failed (P&L $111k vs $121k at 1x; drawdown $32k vs $70k) | [summary](2026-11-02-friday-entry/summary.md) · [report](2026-11-02-friday-entry/2026-11-02-friday-entry.pdf) |
| 2026-11-02 | [Selling a 20-delta put instead of 25-delta raises the stress-sized book's net P&L](2026-11-02-lower-delta/README.md) | Gabe Soler (PM) | passed (in-sample; hold-out not run; lead mostly August 2015) | [summary](2026-11-02-lower-delta/summary.md) · [report](2026-11-02-lower-delta/2026-11-02-lower-delta.pdf) |
| 2026-11-02 | [A small long call when VIX/VIX3M >= 1.1 cuts the put book's drawdown and tail](2026-11-02-crash-call/README.md) | Gabe Soler (PM) | failed (drawdown slightly worse; $1,250 calls too small) | [summary](2026-11-02-crash-call/summary.md) · [report](2026-11-02-crash-call/2026-11-02-crash-call.pdf) |
| 2026-11-05 | [A learning-to-rank model that picks each day's put delta, or no trade, beats the fixed 25-delta put on Sharpe](2026-11-05-ltr-puts/README.md) | Gabe Soler (PM) | failed (2014-19 Sharpe lower; full-window 0.84 vs 0.52 from a gate that sat out 2020; P&L $80k vs $121k) | [summary](2026-11-05-ltr-puts/summary.md) · [report](2026-11-05-ltr-puts/2026-11-05-ltr-puts.pdf) |
| 2026-11-13 | [An ATM straddle for long gamma and a 20-delta strangle for short gamma make the VRP-band book's daily P&L less volatile](2026-11-13-straddle-strangle/README.md) | Gabe Soler (PM) | failed (daily P&L std $54 vs $36; strangle half +$1,398 alone) | [summary](2026-11-13-straddle-strangle/summary.md) · [report](2026-11-13-straddle-strangle/2026-11-13-straddle-strangle.pdf) |
