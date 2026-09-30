# How Should the Desk Generate Market-State Signals?
*Strategy research · 2026-09-29 · L/S Gamma Desk, QUANTT*

**Question:** look into how signal generation for market state should happen. investigate all posibilities including ML strategies, agentic routing, etc.

**Method:** Searched all 26 papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Previous research (builds on):** [Agent routing](2026-09-27-agent-routing-which-algo-to-run.md) · [ML/RL for RV forecasting](2026-09-27-ml-rl-for-realised-volatility-forecasting.md) · [Volatility surface](2026-09-27-volatility-surface-for-the-strategy.md) · [Leverage effect](2026-09-27-leverage-effect-and-the-ls-gamma-desk.md)

---

## Short answer
Treat signal generation as **three separate layers**, and upgrade each one only when the simpler version has been beaten out of sample:
1. **Inputs:** what the market looks like. The VRP (implied vol minus forecast RV), the IV level, term slope and skew, the VIX term structure, VVIX, RV lags, and trend and momentum.
2. **State estimate:** how confident we are about which regime we're in. Four options, simplest first:
   - fixed thresholds, e.g. a VRP z-score with a dead band
   - a probabilistic regime model (a hidden Markov model) giving regime probabilities
   - an ML model predicting which trade will pay
   - RL used to pick and blend the forecasts that feed the signal
3. **Decision:** which algo to run, how big, or stay flat. Again three options: a rule table, a trained RL policy, or an LLM agent choosing from a fixed menu.

The papers agree on four things:
- **A three-state rule** (long / short / flat) based on RV versus IV is the natural starting point. OPHR uses exactly that as its starting policy.
- **Regime *uncertainty* should cut position size,** not just regime labels.
- **Forecast accuracy isn't the goal. P&L is.**
- **Agents are only competitive with good rules,** not clearly better.

## What the papers say

### 1. The core signal: realized vs implied vol, with a "do nothing" zone
- **OPHR's starting policy is a three-state rule.** It:
  > "generates long/short signals by comparing the future RV and current IV" (Chen, Cai, Qin & An, *OPHR*, p. 7)

  It goes long if future RV is above IV by more than a margin, short if below by more than a margin, and otherwise flat. It uses *future* RV, which is only possible in training. The authors call it:
  > "While inherently sub-optimal, its action aligns with desirable and profitable trading behaviors, significantly reducing the exploration burden, accelerating convergence." (*OPHR*, p. 7)
- **OPHR's learned agent makes the same three-way choice:**
  > "determines the target position (long/short/neutral) of options at each step." (*OPHR*, p. 5)
- **PRISM normalizes the VRP within each regime before using it:**
  > "The VRC derivatives team enters a long gamma position when PRISM's normalized VRP signal exceeds the VRC minimum threshold" (Verma 2026, *PRISM*, p. 27)

  The signal is a z-score: the VRP's distance from its regime-specific average, in regime-specific standard deviations.

### 2. Probabilistic regimes, and sizing down when uncertain
- **PRISM puts its regime estimate at the center of everything:**
  > "A stale or inaccurate regime estimate is the single largest source of edge erosion in gamma scalping" (*PRISM*, p. 24)
- **It reports high accuracy, but only in simulation:**
  > "with the VRC particle filter achieving regime identification accuracy exceeding 89% and detection latency under two trading days" (*PRISM*, p. 2)
- **It scales size down when unsure:**
  > "with an entropy-based uncertainty penalty that automatically scales VRC's allocations down during regime ambiguity" (*PRISM*, p. 2)

  Entropy here measures how spread out the regime probabilities are, i.e. how unsure the model is. PRISM is a non-peer-reviewed whitepaper and all its numbers are simulated.
- **Regimes change quickly:**
  > "term structure and skew swing within weeks" (*Deep Hedging with RL: A Practical Framework*, p. 2)
- **Even news-based signals behave differently by regime:**
  > "the contribution of news is strongly regime-dependent" (Rahimikia, Zohren & Poon, *RV Forecasting via Financial Word Embedding*, p. 5)

### 3. Which inputs matter
- **For forecasting vol:**
  > "the most influential drivers of volatility, namely RVD, RVW, IV and M1W" (Christensen, Siggaard & Veliyev 2022, *A Machine Learning Approach to Volatility Forecasting*, p. 24, printed p. 23)

  These are daily RV, weekly RV, implied vol, and the past week's return.
- The surface level and term slope also matter most for hedging decisions (see the vol-surface report).

### 4. ML: better forecasts don't automatically mean better trades
- **OPHR's machine-learning baselines forecast vol well but lost:**
  > "they fail to bridge the gap between forecasting RV and optimizing path-dependent PnL outcomes in options trading" (*OPHR*, p. 9)

  This argues for training or at least *evaluating* signals on trade outcomes, not just forecast error.
- **Pre-trained forecasting models need ongoing retraining:**
  > "incremental fine-tuning, which allows the model to adapt to new financial return data over time, is essential for learning volatility patterns effectively." (Goel, Pasricha, Magris & Kanniainen 2025, *Foundation Time-Series AI Model for RV Forecasting*, p. 1)

### 5. RL for choosing and blending forecasts
- **The problem RL is trying to solve:**
  > "the challenge of outperforming the simple average when aggregating forecasts from diverse methods." (Medeiros & Pinto 2025, *Time Series Embedding and Combination of Forecasts: An RL Approach*, p. 1)
- **Their result:**
  > "we found that RL effectively detects and switches to the most suitable model as needed, with better empirical results than the simple average." (Medeiros & Pinto, p. 8)

  It doesn't always win:
  > "However, for NGDP and PCE, RL ranked third, falling short of a superior outcome." (Medeiros & Pinto, p. 7)
- **The same idea in electricity load forecasting:**
  > "a Q-learning agent learns the optimal policy of selecting the best forecasting model for the next time step, based on the model performance." (*RL based Dynamic Model Selection for Short-Term Load Forecasting*, p. 1)
- **Applied to volatility, blending three deep networks on SPX RV:**
  > "Finally, the optimal weights of the above three models are determined by the Q-learning algorithm to construct an integrated model" (Yu, Lin, Hou & Zhang 2023, *Novel Optimization Approach for RV Forecast … Deep RL*, p. 1)

### 6. Agents and rules for the final decision
- **Where an LLM agent belongs:**
  > "calculations and low-latency execution can be compiled into the surrounding system, while the agent is most valuable when reserved for the judgment margin." (Cheng, Granger, Shi & Strela 2026, *Agents Are Not Algorithms*, p. 26, printed p. 25)
- **Rules are a strong benchmark:**
  > "These outcomes are competitive with a fully compiled algorithm that uses a 5-cent threshold to accept tenders, which earns mean NLV of $44.5 thousand with a Sharpe ratio of 2.49." (same, p. 23, printed p. 22)

  NLV is net liquidation value, the account's ending value.
- **In practice, rules still dominate:**
  > "yet production overlays still revolve around a few manually tuned rules." (*Practical Framework*, p. 2)

  The same paper's emphasis on a leak-free environment matters for any learned signal:
  > "we design a leak-free environment, a cost-aware reward function" (*Practical Framework*, p. 1)

## The options, side by side

| Layer | Approach | Evidence in library | Pros | Cons | Data needed |
|---|---|---|---|---|---|
| State | **Threshold rule** (VRP dead band, VRP z-score, term-structure gate) | OPHR (starting policy), PRISM (z-score and gates) | Transparent, fast, easy to backtest; the benchmark everything must beat | Thresholds are hand-set and regimes shift | Pipeline features today |
| State | **Probabilistic regime model** (hidden Markov / Markov switching) | PRISM (simulated only); web studies on S&P 500 | Gives probabilities, so uncertainty can scale size | Regime labels lag; many settings to fit | VIX, term structure, RV history |
| State | **ML predicting the payoff** (e.g. whether short gamma pays over the next N days) | Christensen (for forecasting); OPHR warns about the forecast vs P&L gap | Captures non-linear patterns; can target P&L directly | Needs labelled history of trade outcomes; overfitting risk | Backtest data (R2) |
| Forecast input | **RL picking or weighting forecasters** | Medeiros & Pinto; DMS; Yu et al. | Adapts when the best model changes | Often only slightly beats a simple average | Several forecasters running side by side |
| Decision | **Rule table** (state → algo) | PRISM gates; *Practical Framework* | Auditable | Rigid | — |
| Decision | **RL policy** (end-to-end) | OPHR | Optimizes P&L directly | Data-hungry; tested on crypto only | Long option backtests |
| Decision | **LLM agent** choosing from a fixed menu | Cheng et al. | Handles unusual situations; explains itself | Only matched a rule; can't be fairly backtested | Pre-computed features |

## How the papers connect
- **One pattern:** every system turns the RV vs IV gap into three actions (long, short, flat), with a band of "no trade" in the middle: OPHR's starting policy, OPHR's learned agent, and PRISM's z-score gate.
- **PRISM and OPHR differ** in how they model state. PRISM estimates regime probabilities explicitly and sizes by confidence. OPHR learns the state implicitly from features.
- **The RL-combination papers** (Medeiros & Pinto, DMS, Yu et al.) improve the *forecast input*, not the trade decision. Medeiros & Pinto are candid that beating a simple average is hard.
- **Cheng et al. and the *Practical Framework*** both say rules stay competitive. Learned or agent layers must earn their place against them.

## Relevance to the LS Gamma desk
These are suggestions, not decisions the desk has made:
- **What already exists:**
  - pipeline features: RV lags, VIX / VIX9D / VIX3M ratios, VIX percentile, VVIX, trend, rf, ATM IV per expiry
  - `forecasting/GARCH.py`
  - 10 execution algos, and `Hedging/`
  - the v1 logic on `archive/v1-ls-gamma`, which already had `signals.py` and `features.py` (a regime file)
- **A staged plan:**
  1. **v0, rule baseline (build first).** VRP = ATM IV at the target tenor minus the forecast RV. Go long gamma above +band, short gamma below −band, otherwise flat. Add a VIX term-structure gate. You set the bands, tenor and gate. This is OPHR's starting policy with a forecast in place of future RV.
  2. **v1, regime probabilities.** Fit a 2–3 state hidden Markov model on VIX, term slope and RV, and **scale size by confidence** (PRISM's idea), not just by the label.
  3. **v2, ML on outcomes.** Using R2 history, train a classifier on "did short/long gamma structure X pay over the next N days", with walk-forward splits.
  4. **v3, routing.** An RL policy (OPHR-style) or an LLM agent choosing from the algo menu, fed the same pre-computed features. The LLM version is forward paper-tested only.
- **Forecast input,** alongside: HAR, then HAR-X, then random forest (from the RV report). Optionally an RL or simple-average combiner across the forecasters.
- **Evaluation rules for every version:**
  - no lookahead, with walk-forward splits
  - costs included
  - judged on strategy P&L and drawdown, not just forecast error
  - each version must beat the previous one out of sample before it replaces it
- **Log the state** (features, regime probabilities, chosen action) every day in the pipeline output, so signals can be audited later.

## Gaps and open questions
- **No peer-reviewed SPY options study** in the library tests regime-conditioned long/short gamma selection end to end. PRISM is simulated and a whitepaper; OPHR is crypto.
- **Backtesting option structures needs option prices.** R2 has trades, not quotes, so fitted smiles are needed to price structures (vol-surface report).
- **Labels:** "which structure would have paid" depends on your exits and hedging rules. Fix those rules first, or the labels change under you.
- **RL combination evidence is thin for volatility.** One ESWA paper on SPX/SSEC/FTSE; the other two are macro and load forecasting.
- **Regime models lag.** PRISM's claimed detection lag of under 2 days is simulated. Real hidden Markov models often switch late, right when gamma matters most.

## Sources
**Repo papers used, with pages cited:**
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf` (pp. 5, 7, 9)
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf` (pp. 2, 24, 27)
- `RL Approach to forecasts.pdf`: Medeiros & Pinto 2025 (pp. 1, 7, 8)
- `1811.01846v1.pdf`: *RL based Dynamic Model Selection for Short-Term Load Forecasting* (p. 1)
- `1-s2.0-S0957417423013829-main.pdf`: Yu, Lin, Hou & Zhang 2023 (p. 1)
- `2505.11163v1.pdf`: Goel, Pasricha, Magris & Kanniainen 2025 (p. 1)
- `A-machine-learning-approach-to-volatility-forecasting.pdf`: Christensen et al. (p. 24)
- `Realised-Volatility-Forecasting-Machine-Learning-via-Financial-Word-Embedding.pdf`: Rahimikia et al. (p. 5)
- `Deep-Hedging-with-Reinforcement-Learning-A-Practical-Framework-for-Option-Risk-Management.pdf` (pp. 1, 2)
- `Agents-Are-not-Algorithms.pdf`: Cheng et al. (pp. 23, 26)

**Checked, not about signal generation:** the deep hedging and hedging papers (they decide hedge size, not trade direction), `2305.04137v2.pdf`, `24-013 PIER Paper Submission.pdf`, `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`, `Volatility-Forecasting-and-Volatility-Risk-Premium.pdf`, `When-You-Hedge-Discretely-…pdf`. Those are covered in the earlier reports.

**Web sources (outside the repo):**
- [Hamilton 1989, *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle*](https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf) (Econometrica 57(2); the linked PDF is Hamilton's regime-switching overview): the original Markov-switching model
- [Blake, Gandhi & Jakkula 2025, *Improving S&P 500 Volatility Forecasting through Regime-Switching Methods* (arXiv)](https://arxiv.org/abs/2510.03236): soft Markov switching and clustering approaches on S&P 500, 2014–2025
- Also seen, not reviewed: [Adaptive hierarchical HMMs for structural market regimes](https://www.mdpi.com/1911-8074/19/1/15); [continuous HMMs for SPY returns](https://arxiv.org/pdf/2606.23492)

**Suggested papers to add to `docs/papers/`:**
1. **Hamilton 1989:** the foundation for any hidden Markov regime model the desk builds.
2. **Blake et al. 2025:** a recent S&P 500 comparison of regime methods for vol forecasting, directly on the desk's underlying.
3. **Ye et al. 2026, *The Alpha Illusion*** (from the agent-routing report): evaluation standards before trusting any LLM-generated signal.
