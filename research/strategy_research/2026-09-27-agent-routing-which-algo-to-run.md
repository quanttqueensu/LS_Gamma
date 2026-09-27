# Using an Agent to Decide Which Algo to Run
*Strategy research · 2026-09-27 · L/S Gamma Desk, QUANTT*

**Question:** look into how an agent can be used to decide which algo to run. this should be very similar to the agents are not algorithms paper

**Method:** Searched all 22 papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Related research:** [Deep hedging as the gamma scalping P&L driver](2026-09-27-deep-hedging-as-gamma-scalping-pnl-driver.md) (covers OPHR's hedger-routing agent)

---

## Short answer
*Agents Are Not Algorithms* (Cheng, Granger, Shi & Strela 2026) gives a clear design rule: use the LLM agent only for the sparse **judgment** decision, feed it **pre-computed numbers**, and hand everything **time-sensitive to compiled code**. Done that way, their agent became competitive with a fixed-rule algorithm. When the agent also ran the fast execution loop, it did much worse.

For the desk this maps directly:
- **The agent's job:** the once-a-day choice of which `LG_`/`SG_` algo to run, or to stay flat.
- **Its inputs:** the pipeline's features (RV forecast, VRP, VIX term structure, VVIX, trend, ATM IV), calculated beforehand.
- **Compiled code, never the agent:** strike selection, order execution (`broker.py`) and intraday hedging (`Hedging/`).

The paper does **not** show that an agent beats a well-designed rule. The rule stayed about as good. So the agent must be tested against a simple compiled router. Separately, an LLM can't be backtested fairly on history it may have seen during training, so forward paper trading is the real test.

## What the papers say

### 1. Agents reason when the decision is made, and that takes time
- **What makes an agent different from an algorithm:**
  > "Agentic AI systems built on large language models reason about each decision in real time rather than executing a pre-specified policy." (Cheng, Granger, Shi & Strela 2026, *Agents Are Not Algorithms*, p. 1)
- **An RL policy trained in advance counts as an algorithm, not an agent:**
  > "Algorithms, whether rule-based or learned through reinforcement learning before deployment, represent the fully compiled policy endpoint." (Cheng et al., p. 2, printed p. 1)
- **The paper doesn't claim agents win:**
  > "To be clear, our question is not whether agents or algorithms dominate, but how and where decision-time reasoning is valuable." (Cheng et al., p. 2, printed p. 1)

### 2. The task splits into judgment and speed
- **Their task has the same two parts as the desk's:**
  > "Tender acceptance rewards judgment: the trader must evaluate quoted edge, displayed liquidity, remaining time, inventory, and penalties. Execution rewards speed" (Cheng et al., p. 3, printed p. 2)

  For them, "tender acceptance" means deciding whether to take a client's block trade. For the desk, the equivalent judgment is which algo to run today.
- **Reasoning helps the decision but hurts execution:**
  > "Reasoning improves the agent's intended decisions and the quality of trades it does complete, but delay creates a wedge between intention and realized trading performance." (Cheng et al., p. 4, printed p. 3)
- **Slow decisions are where reasoning pays:**
  > "In our slowest treatment, the same agent earns the highest average profits." (Cheng et al., p. 4, printed p. 3)
- **More reasoning isn't automatically better:**
  > "The robust feature is the non-monotonicity: increasing decision-time reasoning does not mechanically improve trading performance." (Cheng et al., p. 25, printed p. 24)

  The best setting depends on the model:
  > "For the Anthropic models we test, performance is highest with extended thinking turned off and declines as the reasoning budget rises." (Cheng et al., p. 6, printed p. 5)

### 3. The architecture that worked
- **Pre-computed decision support, with no recommendation attached:**
  > "This decision-support block reports book-based tender edge, projected inventory, limit-breach indicators, and flattening costs, but does not recommend an action." (Cheng et al., p. 22, printed p. 21)

  > "In the low-reasoning cell, mean NLV rises from $18.6 thousand for the baseline agent to $30.4 thousand with pre-computed calculations." (Cheng et al., p. 23, printed p. 22)

  NLV is net liquidation value, i.e. the account's ending value.
- **The agent only makes the judgment call; compiled code executes:**
  > "The reasoning-off agent with compiled unwind earns a slightly lower mean NLV of $44.5 thousand, is profitable in every session, and has the highest Sharpe ratio in this architecture, 2.85." (Cheng et al., p. 23, printed p. 22)

  > "These outcomes are competitive with a fully compiled algorithm that uses a 5-cent threshold to accept tenders, which earns mean NLV of $44.5 thousand with a Sharpe ratio of 2.49." (Cheng et al., p. 23, printed p. 22)
- **The design rule in one sentence:**
  > "calculations and low-latency execution can be compiled into the surrounding system, while the agent is most valuable when reserved for the judgment margin." (Cheng et al., p. 26, printed p. 25)
- **For their order-routing task, the fixed rule won:**
  > "when the routing, tender-evaluation, and unwind logic can be specified in advance, the algorithm avoids much of the real-time deliberation cost faced by the agent." (Cheng et al., p. 74, printed p. 73)

### 4. An RL agent picking the strategy (OPHR)
- **Two agents: one picks the position, one picks the hedger:**
  > "Option Position Agent (OP-Agent) controlling the long/short of volatility, and ii) Hedger Routing Agent (HR-Agent) selecting the optimal Hedgers with different risk preferences to perform dynamic Delta hedging based on positions and market conditions." (Chen, Cai, Qin & An, *OPHR*, p. 2)
- **The router picks, and the chosen hedger executes:**
  > "The HR-Agent makes a decision every N steps, and the selected Hedger executes hedging at each step." (*OPHR*, p. 5)
- **Both share one goal:**
  > "Both agents share the common objective of maximizing portfolio net value while managing risk exposure." (*OPHR*, p. 4)
- **Training starts from an imperfect rule, then improves on it:**
  > "we first distill a sub-optimal Oracle policy to OP-Agent, then alternatively train HR-Agent and OP-Agent." (*OPHR*, p. 2)

### 5. A fixed-rule router (PRISM)
- **PRISM routes with fixed "gates" instead of an agent:**
  > "The VRC investment committee requires that all four of the following gates pass before the VRC derivatives desk may initiate any long gamma position." (Verma 2026, *PRISM*, p. 34)

  The four gates are a VRP threshold, an arbitrage condition, a minimum cost-adjusted Sharpe, and regime certainty.
- **One gate blocks trades while the regime is unclear:**
  > "This gate prevents VRC from entering a long gamma position during regime transition ambiguity" (*PRISM*, p. 35)

  PRISM is a non-peer-reviewed whitepaper and its results are simulated.

## How the papers connect

| Paper | Builds on / agrees with | Differs from | Key contribution |
|---|---|---|---|
| Cheng et al. 2026, *Agents Are Not Algorithms* | Agrawal, Gans & Goldfarb (prediction vs judgment); Lopez-Lira 2025 | Treats RL policies as compiled algorithms | Place the agent only on the judgment decision; pre-compute its inputs; compile execution |
| OPHR | Murray et al. 2022; Buehler et al. | An RL router, trained before deployment, i.e. "compiled" in Cheng's terms | Separate agents for vol position and hedger choice |
| PRISM | Whalley–Wilmott; HAR-RV | No learning; fixed gates | A rule-based router: VRP, regime and cost gates |
| *The Alpha Illusion* (web) | — | End-to-end LLM trading papers | Reported LLM alpha is not deployment evidence |
| *Agentic Trading* survey (web) | — | — | 77 studies; weak evaluation standards |

- **Three designs, same shape.** Cheng's agent-plus-compiled-execution, OPHR's routing agent over fixed hedgers, and PRISM's gate rules all separate *choosing* from *executing*. They differ in whether the choice is made by reasoning at the time (LLM), a trained policy (RL), or fixed rules.
- **The rule is always a strong baseline.** Cheng's fixed rule matched the best agent setup and beat the agent on the routing task. PRISM runs entirely on rules.
- **Pre-computed inputs matter.** Cheng's decision-support gain matches OPHR giving its router Greeks and position data as inputs.

## Relevance to the LS Gamma desk
These are suggestions, not decisions the desk has made:
- **The desk's current structure already matches Cheng's winning architecture.**

  | Cheng et al. | LS Gamma desk |
  |---|---|
  | Tender judgment (agent) | Daily choice of which `LG_`/`SG_` algo to run, or none (the future signals/agent layer) |
  | Decision support (pre-computed, no recommendation) | `pipeline/` output: `features` (RV/HAR, trend, VIX term structure, VIX percentile, VVIX, rf), `atm_iv`, plus the RV forecast and VRP |
  | Compiled unwind execution | `broker.submit()`, and the algo files' fixed legs |
  | Continuous trading loop kept away from the agent | `Hedging/` hedgers running on a schedule, with no LLM in that loop |
- **A daily decision is the "slow market" case,** where Cheng et al. found reasoning pays off most (p. 4). That's an inference: their fastest decisions were seconds, the desk's is daily.
- **Constrain the agent's output.** Suggestion: it returns only an algo name from a fixed menu (the registry of `LG_`/`SG_` algos plus "stay flat") and a short reason. Code checks that choice before anything runs. The agent never calls `broker` directly, and never picks strikes unless that's added deliberately later.
- **Test against three routers:**
  1. **A compiled rule router**, PRISM-style gates. For example, "VRP above threshold → short gamma structure X; term structure inverted → iron condor", with thresholds you set. This is the baseline that must be beaten.
  2. **An LLM agent** with the pipeline features as input, choosing from the menu. Test its reasoning setting (off / low / higher), because the best level depends on the model (p. 6, p. 25).
  3. **Optionally, an RL router** like OPHR's, which is compiled in Cheng's terms. It needs historical training data, e.g. the club's R2 dataset.
- **Log every decision:** the inputs, the menu choice and the agent's stated reason. Cheng et al. studied recorded reasoning (p. 4) and it makes the router auditable for the desk. `research/Agentic_Routing/` is the natural home for these experiments.

## Gaps and open questions
- **Different task.** Cheng et al. study block-trade acceptance and inventory unwinding in a simulator (Rotman Interactive Trader), over seconds and minutes. They don't test picking between options strategies, or daily decisions.
- **Agent ≈ rule, not agent > rule.** In their best setup the agent was only *competitive* with a 5-cent threshold rule. Whether an agent adds value over a simple VRP/regime rule for the desk is untested.
- **Backtesting an LLM is contaminated.** An LLM may have seen historical market outcomes in its training data (*Alpha Illusion*, web). Running it over 2014–2025 history isn't a fair test, so forward paper trading is the credible evidence. An RL or rule router doesn't have this problem.
- **Model- and prompt-dependent.** Cheng et al. find the best reasoning level differs across models and providers. The prompt, the menu design and the input format all need testing.
- **Where strike selection lives.** The papers don't say whether choosing strikes and expiries is "judgment" or should be compiled. Starting compiled is the safer default.

## Sources
**Repo papers used, with pages cited:**
- `Agents-Are-not-Algorithms.pdf`: Cheng, Granger, Shi & Strela 2026, *Agents Are Not Algorithms: The Tradeoffs of Decision-Time Reasoning in AI Trading* (pp. 1, 2, 3, 4, 5, 6, 22, 23, 25, 26, 74)
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf`: Chen, Cai, Qin & An (pp. 2, 4, 5)
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf`: Verma 2026 (pp. 34, 35)

**Checked, nothing on choosing between strategies:** the other 19 papers. The deep hedging and RL papers choose hedge sizes, not strategies. The forecasting and VRP papers provide the inputs, not the routing.

**Web sources (outside the repo):**
- [Cheng et al. 2026 on SSRN](https://papers.ssrn.com/abstract=6713620), [author page](https://inghawcheng.github.io/), [ML Quants summary](https://mlquants.substack.com/p/agents-are-not-algorithms-the-tradeoffs)
- [Ye et al. 2026, *The Alpha Illusion: Reported Alpha from LLM Trading Agents Should Not Be Treated as Deployment Evidence*](https://arxiv.org/abs/2605.16895)
- [Xia et al. 2026, *Agentic Trading: When LLM Agents Meet Financial Markets* (survey of 77 studies)](https://arxiv.org/abs/2605.19337)

**Suggested papers to add to `docs/papers/`:**
1. **The Alpha Illusion (2026):** how to evaluate an LLM router without fooling yourself; minimum reporting standards.
2. **Agentic Trading survey (2026):** a map of the LLM-agent designs that have been tried, and which studies meet basic evidence standards.
3. **Murray et al. 2022:** the hedger family OPHR's router chooses from; useful if the desk builds a routing agent over `Hedging/`.
4. **Agrawal, Gans & Goldfarb, *Prediction, Judgment, and Complexity*:** the prediction-vs-judgment framing Cheng et al. build on. Found only through their references, not on the web.
