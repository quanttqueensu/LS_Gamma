# Machine Learning and Reinforcement Learning for Realised Volatility Forecasting
*Strategy research · 2026-09-27 · L/S Gamma Desk, QUANTT*

**Question:** Machine learning/reinforcement learning for Realised volatility forecasting

**Method:** Searched all 22 papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Related research:** [Leverage effect and the desk](2026-09-27-leverage-effect-and-the-ls-gamma-desk.md) (GJR-GARCH / LHAR suggestions) · [Agent routing](2026-09-27-agent-routing-which-algo-to-run.md) · [Deep hedging as the P&L driver](2026-09-27-deep-hedging-as-gamma-scalping-pnl-driver.md)

---

## Short answer
**Machine learning can beat HAR models for realized volatility, mostly at longer horizons, but HAR stays a tough baseline.** Christensen, Siggaard & Veliyev find random forests and neural networks beat the HAR family even using only HAR's own inputs (daily, weekly and monthly RV). The gains grow with the forecast horizon. The most useful inputs are recent RV, implied vol, and recent returns.

**Reinforcement learning isn't used to produce the forecast itself** in any paper in the library. Where RL shows up, it's in two other roles:
1. **Choosing or blending forecasting models** over time (web).
2. **Skipping the forecast** and learning the vol-trading decision directly, which is what OPHR does. OPHR's point is that ML forecasters with good accuracy still failed to make money.

**For the desk:** build up from GARCH to HAR, then HAR with implied vol, then a random forest or small network, all on the same inputs. Judge them by trading P&L as well as forecast error.

## What the papers say

### 1. ML vs HAR: ML wins, especially at longer horizons
- > "ML is competitive and beats the HAR lineage, even when the only predictors are the daily, weekly, and monthly lags of realized variance. The forecast gains are more pronounced at longer horizons." (Christensen, Siggaard & Veliyev 2022, *A Machine Learning Approach to Volatility Forecasting*, p. 1)
- Without heavy tuning:
  > "ML is implemented with minimal hyperparameter tuning." (same, p. 1)
- **Which models:**
  > "The random forest and neural networks are preferred among ML algorithms and significantly improve prediction relative to HAR." (same, p. 36, printed p. 35)
- **But HAR is hard to beat on risk measures:**
  > "Interestingly, the basic HAR model is remarkably solid and tough to beat in the VaR framework." (same, p. 33, printed p. 32)
- **Their data is single stocks, not an index:**
  > "The empirical investigation is based on high-frequency data from 29 of the 30 Dow Jones Industrial" (same, p. 12, printed p. 11)

### 2. Which inputs matter
- > "the most influential drivers of volatility, namely RVD, RVW, IV and M1W" (Christensen et al., p. 24, printed p. 23)

  These are daily RV, weekly RV, implied volatility, and 1-week momentum (the past week's return).
- **The past week's return works in the leverage-effect direction:**
  > "the marginal association between RVt and M1W is negative." (same, p. 24, printed p. 23)

  So recent losses predict higher volatility.

### 3. News and text help as an add-on, not a replacement
- > "News-only forecasts contain useful predictive information but generally do not outperform strong volatility-history benchmarks." (Rahimikia, Zohren & Poon, *Realised Volatility Forecasting: ML via Financial Word Embedding*, p. 1)
- > "combining stock-related news forecasts with a strong volatility-history benchmark lowers forecast losses for several specifications and increases realised utility" (same, p. 1)

### 4. Data matters more than model size
- **Rahimikia et al. summarize Liu et al. (2026):**
  > "Liu et al. (2026) show that neural-network volatility forecasting depends importantly on the estimation regime and data scale, with global estimation and larger, more diverse training samples generating substantially greater gains than increases in model size or changes in network architecture." (Rahimikia et al., p. 3)

  "Global estimation" means training one model across many assets rather than one model per asset.
- **How RV is measured sets the bar:**
  > "consistent with Liu et al. (2015), who highlight the difficulty of significantly beating the 5-minute RV benchmark." (same, p. 22)

  Both main papers measure RV from 5-minute intraday returns.

### 5. Using realized measures inside GARCH-type models
- > "we find that the Realized GARCH model significantly outperforms conventional GARCH models." (Hansen, Huang, Tong & Wang 2021, *Realized GARCH, CBOE VIX, and the VRP*, p. 1)

  They test on the S&P 500.

### 6. Accurate forecasts don't guarantee P&L
- **OPHR's machine-learning baselines forecast vol but don't make money:**
  > "Similarly, ML baselines (GBDT, MLP, LSTM, DeepVol, GARCH) struggle with profitability despite occasionally achieving lower volatility" (*OPHR*, p. 9)

  > "they fail to bridge the gap between forecasting RV and optimizing path-dependent PnL outcomes in options trading" (*OPHR*, p. 9)

  OPHR's answer is RL that learns the long/short vol decision directly, rather than a better forecast.

### 7. Practitioner use and a weak dissenting paper
- **PRISM uses a HAR-based model to drive its VRP entry signal:**
  > "as computed by the VRC HAR-RV-Regime model" (Verma 2026, *PRISM*, p. 35)

  PRISM is a non-peer-reviewed whitepaper.
- **Cheng (2015) claims implied vol beats GARCH and that there is no VRP:**
  > "model-free implied volatility is more accurate to forecast the future volatility and the volatility risk premium does not exist." (J. Cheng 2015, *Volatility Forecasting and Volatility Risk Premium*, p. 1, printed p. 98)

  This is a 5-page paper from a low-profile journal. It conflicts with the rest of the library, which finds a sizable VRP (Hansen et al.; Cheng, Renault & Sangrey), so treat it with caution.

## How the papers connect

| Paper | Builds on / agrees with | Differs from | Key contribution |
|---|---|---|---|
| Christensen, Siggaard & Veliyev 2022 | Corsi 2009 (HAR, web) | HAR-only studies | Random forests and neural nets beat HAR, more so at longer horizons; RV lags, IV and momentum matter most |
| Rahimikia, Zohren & Poon | HAR family; Liu et al. 2026 | News-only approaches | Text helps only when combined with an RV-history model; data scale beats model size |
| Hansen et al. 2021 | GARCH, EGARCH | Plain GARCH | Adding realized measures to GARCH improves S&P 500 forecasts |
| OPHR | Deep RL | Forecast-first pipelines | Forecast accuracy doesn't translate into P&L; RL learns the trading decision directly |
| PRISM | HAR | Not peer-reviewed | HAR-based VRP signal used for trading |
| Cheng 2015 | Britten-Jones & Neuberger | Most of the library | Claims implied vol dominates and there's no VRP; weak evidence |

- **Agreement:** HAR-type inputs (daily, weekly and monthly RV) are the core of every serious model, and ML adds value on top of them rather than replacing them.
- **Implied vol is a key input** in Christensen et al. and in Hansen et al.'s Realized GARCH, which uses VIX. That fits the desk, since the pipeline already collects VIX and ATM IV.
- **The disagreement is about what counts as success.** The forecasting papers judge by forecast error, while OPHR judges by P&L and finds the two can diverge.

## Relevance to the LS Gamma desk
These are suggestions, not decisions the desk has made:
- **What already exists:** `forecasting/GARCH.py` (symmetric GARCH(1,1)); pipeline features `rv_d`, `rv_w`, `rv_m` (the HAR inputs, from daily Garman-Klass RV), `ret`, VIX and `atm_iv`; and a `research/RV_Forecasting/` folder.
- **A model ladder**, each step using the `new-forecaster` skill and the same `fit`/`predict` interface:
  1. **HAR** on `rv_d`, `rv_w`, `rv_m`: the baseline everything must beat.
  2. **HAR-X**: add VIX or ATM IV, and the past week's return. These are Christensen et al.'s most influential inputs, and the return term is also the leverage effect.
  3. **LHAR / GJR-GARCH**, from the leverage report.
  4. **Random forest or a small neural network** on the same inputs. This is where the evidence says ML helps, especially for longer horizons like the 7–60 day tenors the desk trades. That's an inference: their longest horizon is monthly.
- **Evaluate two ways:**
  1. **Forecast error**, out of sample with walk-forward windows, using QLIKE or MSE.
  2. **Signal P&L:** whether the forecast's VRP signal picks winning long/short gamma trades. OPHR warns these two can disagree.
- **Where RL fits:**
  - **Not as the forecaster.**
  - **As a model picker:** choosing or weighting forecasters over time, the same idea as the agent-routing report.
  - **As OPHR-style end-to-end vol timing:** a separate research track.
- **Lower priority:** news and NLP features. They help only on top of a strong RV model, and they add data plumbing.

## Gaps and open questions
- **Daily vs intraday RV.** The papers use 5-minute RV. The desk's live RV is daily Garman-Klass, which is noisier and misses overnight moves. yfinance only serves about 60 days of intraday data. The club's R2 bucket (checked 2026-09-27) has **intraday SPY option trades** (millisecond timestamps, 2014-06 to 2026-07) but **no intraday SPY stock prices**: SPY is daily only (CRSP), and there's no TAQ data. A 5-minute SPY price series could be *backed out* from the option trades using put-call parity (call minus put at the same strike and expiry ≈ SPY minus the discounted strike). It would be noisier than real stock prices, but it would give intraday RV back to 2014. Better RV input may matter more than a better model.
- **Index vs single stocks.** Christensen et al. forecast Dow component stocks, not SPY. Index vol has a stronger leverage effect and fewer idiosyncratic jumps, so gains may differ.
- **Data scale.** ML gains depend on large, diverse training data (Liu et al. via Rahimikia). One asset's daily history is small; using a long SPY history (yfinance goes back to 1993) or training across several assets could help.
- **Horizon match.** The papers test 1-day to 1-month horizons. The desk's relevant horizon is the option's remaining life (1–60 DTE).
- **RL for forecasting is thin.** The web sources on RL model selection are recent or from other domains (load forecasting, M4, surveys), not tested on SPY RV.

## Sources
**Repo papers used, with pages cited:**
- `A-machine-learning-approach-to-volatility-forecasting.pdf`: Christensen, Siggaard & Veliyev (pp. 1, 12, 24, 33, 36)
- `Realised-Volatility-Forecasting-Machine-Learning-via-Financial-Word-Embedding.pdf`: Rahimikia, Zohren & Poon (pp. 1, 3, 22)
- `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`: Hansen, Huang, Tong & Wang (p. 1)
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf` (p. 9)
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf` (p. 35)
- `Volatility-Forecasting-and-Volatility-Risk-Premium.pdf`: J. Cheng 2015 (p. 1)

**Checked, nothing on forecasting RV:** the deep hedging and RL hedging papers (they use RV as an input, not a target), `Agents-Are-not-Algorithms.pdf`, `2305.04137v2.pdf`, `24-013 PIER Paper Submission.pdf`, `When-You-Hedge-Discretely-…pdf`, `Hedging-with-Linear-Regressions-and-Neural-Networks.pdf`.

**Web sources (outside the repo):**
- [Corsi 2009, *A Simple Approximate Long-Memory Model of Realized Volatility* (J. Financial Econometrics)](https://academic.oup.com/jfec/article-abstract/7/2/174/856522), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1365738): the original HAR model
- [Medeiros et al. 2025, *Time Series Embedding and Combination of Forecasts: A Reinforcement Learning Approach* (arXiv)](https://arxiv.org/abs/2508.20795): RL for choosing and weighting forecasts; tested on simulated, M4 and SPF data, not volatility
- [Goel, Pasricha, Magris & Kanniainen 2025, *Foundation Time-Series AI Model for Realized Volatility Forecasting* (arXiv)](https://arxiv.org/abs/2505.11163): a fine-tuned TimesFM beats econometric benchmarks
- Also seen, not reviewed: [RL dynamic model selection for load forecasting](https://arxiv.org/pdf/1811.01846); [a deep-RL approach to RV forecast optimization (Expert Systems with Applications)](https://www.sciencedirect.com/science/article/abs/pii/S0957417423013829)

**Suggested papers to add to `docs/papers/`:**
1. **Corsi 2009 (HAR):** the baseline every forecaster on the desk should be compared against.
2. **Goel et al. 2025 (TimesFM for RV):** a modern alternative to training your own ML model; tests incremental fine-tuning.
3. **Medeiros et al. 2025 (RL forecast combination):** the cleanest "RL as model picker" design.
4. **Liu et al. 2026, neural-network volatility forecasting and data scale:** why training data size matters more than architecture. Found only through Rahimikia et al.'s citation; not located on the web.
