# Deep Hedging as the Mechanical P&L Driver for Gamma Scalping
*Strategy research · 2026-09-27 · L/S Gamma Desk, QUANTT*

**Question:** how can reinforcement learning hedging, aka deep hedging be used as the  mechanical PnL driver  for gamma scalping

**Method:** Searched all 21 papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

---

## Short answer
Deep hedging can serve as the mechanical P&L driver for gamma scalping, but only if you change what it's trained to do. In the papers, deep hedging usually minimizes the risk of an option you're hedging. For scalping, the training objective has to become the risk-adjusted P&L of the delta-hedged position after costs. Only OPHR in the library does that (PRISM proposes it).

The edge itself still comes from realized vol differing from implied vol. What the hedging rule controls is how much of that difference you actually capture, and what it costs. The papers point to three places an RL hedger beats a fixed delta-hedging rule:
1. **Costs:** it holds back on trades that aren't worth their cost, e.g. staying slightly under- or over-hedged instead of always going exactly to zero delta.
2. **Market path:** it hedges tightly when the market chops back and forth, and loosely when it trends.
3. **Forward-looking inputs:** it can use the IV surface and the volatility risk premium when deciding what to do.

The main risk: once profit is rewarded, the agent can quietly start taking directional bets. Whether it does depends on how strongly the objective penalizes bad outcomes.

## What the papers say

### 1. For long gamma, hedging is how the P&L is produced
- OPHR states the mechanism directly, and says it differs between long and short gamma:
  > "For long Gamma positions, it acts as a profit mechanism through Γ scalping—systematically buying low and selling high as price fluctuations alter ∆ values. For short Γ positions, it primarily mitigates risk by neutralizing directional exposure." (Chen, Cai, Qin & An, *OPHR*, p. 4)
- The same realized vol can give different P&L depending on the path the price takes, which is why the choice of hedging rule matters:
  > "In oscillating markets, hedging locks in profits when prices return to original levels, while in trending markets, hedging may limit potential gains as prices move consistently in one direction." (*OPHR*, p. 4)
- A good RV forecast alone doesn't produce good P&L. OPHR says the machine-learning forecasting baselines struggled because:
  > "they fail to bridge the gap between forecasting RV and optimizing path-dependent PnL outcomes in options trading" (*OPHR*, p. 9)

### 2. The trade-off an RL hedger must beat: hedging frequency against transaction costs
- Sepp gives a closed-form benchmark for delta hedging when you can only hedge at discrete times and pay costs:
  > "rebalancing the delta-hedge as little as possible increases expected profit. On the other hand, infrequent rebalancing increases P&L volatility." (Sepp 2013, *When You Hedge Discretely*, p. 3)

  At the frequency that maximizes Sharpe ratio:
  > "the expected transaction costs equal to the half of the expected P&L. The optimal frequency is inversely proportional to the square of the transaction costs" (Sepp, p. 12)

  and
  > "the higher is the premium, the more frequent hedging is possible and, as a result, the higher Sharpe ratio is attainable." (Sepp, p. 12)
- PRISM applies the same idea to a threshold on how far delta can drift before you rehedge. When realized vol is beating implied, it widens that threshold:
  > "gamma income partially compensates for the cost of rebalancing, so the urgency to rebalance is reduced." (Verma 2026, *PRISM*, p. 21)

  It then proposes RL as the next step:
  > "a deep reinforcement learning layer that learns the optimal VRC bandwidth function directly from simulated P&L" (*PRISM*, p. 40)

### 3. What deep hedging adds over delta hedging
- **General framework:**
  > "We present a framework for hedging a portfolio of derivatives in the presence of market frictions such as transaction costs, market impact, liquidity constraints or risk limits using modern deep reinforcement machine learning methods." (Buehler, Gonon, Teichmann & Wood, *Deep Hedging*, p. 1)
- **Cost-aware hedge sizes:**
  > "when delta hedging would require shares to be purchased, it tends to be optimal for a trader to be under-hedged relative to delta. Similarly, when delta hedging would require shares to be sold, it tends to be optimal for a trader to be over-hedged relative to delta." (Cao, Chen, Hull & Poulos, *Deep Hedging of Derivatives Using RL*, p. 2)

  and
  > "(Indeed, when trading costs are very high it may be optimal to do no hedging at all.)" (Cao et al., p. 2)
- **Smaller trades and awareness of the volatility risk premium**, tested on real straddles:
  > "First, RL strategies typically rely on smaller trades." (François, Gauthier, Godin & Pérez-Mendoza 2025, *Deep Hedging with Options Using the IV Surface*, p. 3, printed p. 2)

  > "the RL agent learns and adapts to the time-varying variance risk premium, which is a key driver of hedging costs." (same, p. 4, printed p. 3)
- **Switching hedging style with the regime.** OPHR's hedger-routing agent picks from a set of hedgers that range from a normal threshold rule to never hedging:
  > "The red one has a finite threshold (less risk-seeking), and the blue one has an infinite threshold (never hedging, extreme risk-seeking)." (*OPHR*, p. 5)

  The result, in the authors' words:
  > "our HR-Agent optimizes performance by selecting appropriate hedging strategies that lock in profits during volatility spikes while minimizing costs during calmer markets." (*OPHR*, p. 10)

### 4. The danger: rewarding profit can turn hedging into speculation
- How the objective weighs bad outcomes decides whether the agent is still hedging:
  > "We observe that the difference between deep hedging and delta hedging is a speculative overlay if the risk measure considered does not put sufficient relative weight on adverse outcomes." (François, Gauthier, Godin & Pérez Mendoza 2024, *Is the Difference … a Statistical Arbitrage?*, p. 1)

  > "The deep hedging agent is incorporating a strong speculative element in its trading strategy, which is unsuitable in practice." (same, p. 10, printed p. 9)
- The IV-surface paper adds penalty terms to the reward specifically to prevent this:
  > "to ensure that the RL agent learns a true hedging strategy rather than engaging in speculative behavior, we introduce penalty terms in the reward function that discourages excessive risk-taking." (François et al. 2025, p. 3, printed p. 2)

### 5. How strong the evidence is
- **Real S&P 500 data, walk-forward testing:** the RL agent beat delta hedging, but
  > "its performance deteriorates when the risk-awareness parameter is higher." (Bracha, Sakowski & Michańków 2025, *DRL for ATM S&P 500 Options Hedging*, p. 2, printed p. 1)
- **Simple models may capture much of the gain:**
  > "However, a similar benefit arises by simple linear regressions that incorporate the leverage effect." (Ruf & Wang, *Hedging with Linear Regressions and Neural Networks*, p. 1)
- **A practical SPY framework reports weak statistical significance:**
  > "only the GAE policy's test-sample Sharpe is statistically distinguishable from zero" (*Deep Hedging with RL: A Practical Framework*, p. 1)
- **OPHR, the closest paper to the question, was tested on crypto options, not SPY:**
  > "Evaluating our approach using cryptocurrency options data from 2021-2024" (*OPHR*, p. 1)

## How the papers connect

| Paper | Builds on / agrees with | Differs from | Key contribution |
|---|---|---|---|
| Buehler et al., *Deep Hedging* | The foundation | — | Hedging with RL under costs, trained against a risk measure |
| Cao, Chen, Hull & Poulos | Buehler; Kolm & Ritter | Uses a mean + standard-deviation objective | Cost-aware under- and over-hedging; P&L measured at each step works better than tracking cash flows |
| Bracha et al. | Buehler, Cao | Real intraday S&P 500 data | RL beats delta hedging out of sample, less so when more risk-averse |
| François et al. 2025 (IV surface) | Buehler; their own 2024 paper | Hedges with options as well as the underlying | Real straddles 2020–23; uses the volatility risk premium; smaller trades |
| François et al. 2024 (statistical arbitrage) | Horikawa & Nakagawa | GARCH market rather than a complete market | Loosely penalized objectives create a speculative overlay |
| Sepp 2013 | Whalley & Wilmott; Leland | Formulas, not RL | Optimal hedge frequency and thresholds; the benchmark to beat |
| PRISM (whitepaper) | Whalley & Wilmott; Sepp | Not peer-reviewed; results are simulated | A drift threshold that adapts to the regime; RL proposed as the next version |
| OPHR | Buehler; Murray et al. 2022; Hull & White | Optimizes profit, not risk; crypto | One agent picks long/short vol, another picks the hedger |
| Ruf & Wang | — | Skeptical of neural networks | Linear regressions match them on S&P options |
| Cao et al. 2023 (gamma and vega) | Cao 2021 | Neutralizes gamma, the opposite of scalping it | Hedging choices depend on costs and the objective |

- **The papers split on the objective.** Most papers train the agent to *reduce risk*. OPHR and PRISM train or propose training it to *maximize P&L*, which is what "P&L driver" means. The 2024 statistical-arbitrage paper warns that this is exactly where speculation creeps in.
- **They agree on costs and thresholds.** Sepp, PRISM, Cao and the IV-surface paper all find you should rehedge less often, or in smaller steps, than pure delta hedging says. RL learns a smarter version of that threshold.
- **Lineage:** Buehler 2019 leads to Cao 2021 and Murray 2022, which lead to OPHR's set of hedgers. Separately, Whalley & Wilmott lead to Sepp and PRISM, with RL proposed as PRISM's next step.

## Relevance to the LS Gamma desk
These are suggestions, not decisions the desk has made:
- **The desk's code already matches OPHR's structure.** The signals file picks long or short gamma and the structure, like OPHR's position agent. `Hedging/` holds interchangeable hedgers, like OPHR's hedger set. A future router choosing between `delta_hedge` and a deep hedger by regime would be the equivalent of OPHR's hedger-routing agent.
- **Train it on scalping P&L after costs, with a strong tail penalty,** rather than on minimizing hedging error. For example, penalize bad outcomes heavily (a high-confidence CVaR) so it doesn't start speculating.
- **Compare it against three baselines, not just plain delta hedging:** a no-trade threshold à la Whalley–Wilmott, and Sepp's optimal hedging frequency.
- **Treat long and short gamma separately.** Hedging is the profit engine for long gamma but only risk control for short gamma (OPHR p. 4), so one objective probably won't suit both.
- **Start with simple models.** Given Ruf & Wang, try a linear regression or threshold baseline before a deep network.

## Gaps and open questions
- **No paper in the library tests an RL hedger that maximizes scalping profit on SPY.** OPHR is crypto; PRISM is simulated and not peer-reviewed; the SPY and S&P studies minimize risk.
- **Intraday data for training.** The club's R2 bucket has SPY option trades but no intraday SPY prices (according to the R2 guide), and the live pipeline is daily. An intraday hedger would need a separate source of intraday SPY prices.
- **Too little data.** A decade of daily data is only a few thousand samples. That pushes you toward simulated markets (*Deep Hedging: Learning to Simulate Equity Option Markets*, p. 1), and results from simulators may not carry over to the real market.
- **Costs.** Most results assume proportional costs. SPY share hedges on IBKR are cheap, so the cost-driven advantage RL shows may be smaller for the desk.
- **Overnight gaps.** Hedging can't respond to them. OPHR's hedge-frequency results are for crypto, which trades 24/7.

## Sources
**Repo papers used, with pages cited:**
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf` (pp. 1, 4, 5, 9, 10)
- `Deep-Hedging.pdf` (p. 1)
- `Deep-Hedging-of-Derivatives-Using-Reinforcement-Learning.pdf` (p. 2)
- `When-You-Hedge-Discretely-Optimization-of-Sharpe-Ratio-for-Delta-Hedging-Strategy-under-Discrete-Hedging-and-Transaction-Costs.pdf` (pp. 3, 12)
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf` (pp. 21, 40)
- `Is-the-Difference-between-Deep-Hedging-and-Delta-Hedging-a-Statistical-Arbitrage?.pdf` (pp. 1, 10)
- `Deep-Hedging-with-Options-Using-the-Implied-Volatility-Surface.pdf` (pp. 3, 4)
- `Application-of-Deep-Reinforcement-Learning-to-At-the-Money-S&P-500-Options-Hedging.pdf` (p. 2)
- `Hedging-with-Linear-Regressions-and-Neural-Networks.pdf` (p. 1)
- `Deep-Hedging-with-Reinforcement-Learning-A-Practical-Framework-for-Option-Risk-Management.pdf` (p. 1)
- `Gamma-and-Vega-Hedging-Using-Deep-Distributional-Reinforcement-Learning.pdf` (p. 1)

**Relevant but used only as background:**
- `Deep-Bellman-Hedging.pdf`: learns hedging from historical data alone
- `Learning-to-Trade-II-Deep-Hedging.pdf`: lecture notes that cover statistical arbitrage
- `Enhancing-Deep-Hedging-of-Options-with-Implied-Volatility-Surface-Feedback-Information.pdf`: IV-surface inputs; results strongest with costs
- `Deep-Hedging-Learning-to-Simulate-Equity-Option-Markets.pdf`: market simulators for training data

**Checked, nothing on hedging (they're about the forecasting and VRP signal side):**
- `2305.04137v2.pdf` (Chong & Todorov, vol-of-vol)
- `24-013 PIER Paper Submission.pdf` (Cheng, Renault & Sangrey)
- `A-machine-learning-approach-to-volatility-forecasting.pdf`
- `Realised-Volatility-Forecasting-Machine-Learning-via-Financial-Word-Embedding.pdf`
- `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`
- `Volatility-Forecasting-and-Volatility-Risk-Premium.pdf`

**Web sources (outside the repo):**
- [OPHR on OpenReview](https://openreview.net/pdf?id=2p4AtivyZz)
- [Murray et al. 2022, *Deep Hedging: Continuous RL … Multiple Risk Aversions* (arXiv)](https://arxiv.org/abs/2207.07467), [ACM](https://dl.acm.org/doi/abs/10.1145/3533271.3561731)
- [Kolm & Ritter 2019, *Dynamic Replication and Hedging: An RL Approach* (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3281235)
- [Armstrong & Tatlow 2024, *Deep Gamma Hedging* (arXiv)](https://arxiv.org/abs/2409.13567)
- [Cao et al., *Gamma and Vega Hedging* (arXiv)](https://arxiv.org/pdf/2205.05614)

**Suggested papers to add to `docs/papers/`:**
1. **Murray et al. 2022:** the source of OPHR's set of hedgers, trained across many risk-aversion levels at once. It's the most direct template for a family of deep hedgers.
2. **Kolm & Ritter 2019:** the RL hedging paper Cao et al. build on. Simple and practical.
3. **Whalley & Wilmott 1997:** the original no-trade threshold, the baseline any RL hedger must beat. Found only through citations in PRISM and Cao et al., not on the web.
4. **Horikawa & Nakagawa 2024:** the original "deep hedging contains a statistical arbitrage" claim. Found only through its citation in François et al. 2024, not on the web.
