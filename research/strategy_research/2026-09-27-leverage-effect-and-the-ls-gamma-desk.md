# The Leverage Effect and What It Means for the LS Gamma Desk
*Strategy research · 2026-09-27 · L/S Gamma Desk, QUANTT*

**Question:** investigate the leverage effect and its relevance to out LS gamma desk

**Method:** Searched all 21 papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Related research:** [Deep hedging as the gamma scalping P&L driver](2026-09-27-deep-hedging-as-gamma-scalping-pnl-driver.md)

---

## Short answer
The leverage effect is the tendency of volatility to rise when prices fall, and to fall when prices rise. For SPY it is strong, and it gets much stronger in crises. It touches four parts of the desk:
1. **Hedging:** the standard delta assumes implied vol stays put when SPY moves. Because IV actually moves opposite to spot, a straddle or strangle hedged to "zero delta" still carries hidden directional exposure through vega.
2. **Forecasting:** a symmetric GARCH(1,1), like the one in `forecasting/GARCH.py`, ignores the effect. Papers find that models including it forecast equity volatility better.
3. **The VRP signal:** part of what option sellers are paid for is carrying this crash-and-vol-spike risk. Which part, and how much, is disputed between the papers.
4. **Regimes and structure choice:** short gamma gets hit two ways at once in selloffs, through realized moves (gamma) and rising IV (vega). Long gamma benefits two ways in the same scenario.

The two most practical fixes are cheap: a delta that accounts for the spot-vol relationship (a minimum-variance delta), and a forecasting model that includes the leverage effect.

## What the papers say

### 1. What the leverage effect is, and how big it is for the S&P 500
- **Definition:**
  > "Following Black (1976), this negative covariance/correlation between asset return and asset volatility is referred to as leverage effect." (Chong & Todorov 2024, *Volatility of Volatility and Leverage Effect from Options*, p. 1)
- **It spikes in crises.** Estimated from intraday SPX option prices (2016–2020):
  > "the leverage effect increases sharply in magnitude at the onset of the pandemic in the Spring of 2020" (Chong & Todorov, p. 19)
- **It moves with the level of vol, while vol-of-vol stays fairly flat:**
  > "the estimated volatility of volatility exhibits little time series variation while the estimated leverage effect is inversely related to the market volatility." (Chong & Todorov, p. 20)

  "Inversely related" here is literal: the leverage effect is a negative number, so it goes *down* (becomes more negative, i.e. larger in size) when market vol goes up.

  The standard Heston model doesn't reproduce this:
  > "These features of the observed estimates are at odds with those implied by the classical Heston model." (Chong & Todorov, p. 20)
- **Hard to measure from prices alone:**
  > "although we expect the leverage effect to be negative, it is difficult to quantify empirically and its estimate usually is small" (Cheng, Renault & Sangrey 2024, *Identifying the Volatility Risk Price Through the Leverage Effect*, p. 4, printed p. 3)

  Chong & Todorov get around this by estimating it from option prices instead of returns.

### 2. Hedging: the standard delta over-hedges calls and under-hedges puts
- **Why:**
  > "The leverage effect describes the negative correlation between an underlying's price and its volatility." (Ruf & Wang, *Hedging with Linear Regressions and Neural Networks*, p. 2)

  > "Due to the leverage effect, the underlying (implied) volatility tends to go down simultaneously, thus having a negative effect on the option price." (Ruf & Wang, p. 2)
- **The estimated fix points the direction you'd expect:**
  > "The Delta coefficients of calls being smaller than one implies that hedging a short position on a call, one would usually buy less of the underlying than implied by the BS Delta. On the other hand, for hedging a short position on a put, one needs to short more of the underlying." (Ruf & Wang, p. 11)
- **Simple beats fancy.** Regressions that add vega-type terms to delta match neural networks:
  > "All competing methods outperform the BS Delta. Among them, the Delta-Vega-Vanna and (relaxed) Hull-White regressions perform the best" (Ruf & Wang, p. 10)

  > "Hence, the ANN seems to be able to learn the leverage effect, but cannot improve on a simple linear regression involving the relevant option sensitivities." (Ruf & Wang, p. 2)
- **Deep hedging confirms it on recent S&P 500 data.** A delta that uses the volatility smile (which captures how IV moves with spot) keeps up with RL, while the plain delta falls behind:
  > "the RL algorithm with IV information and the smile-implied delta hedging, both of which leverage the IV surface, deliver comparable performance in terms of MSE. They are closely followed by the RL algorithm with restricted information, while the practitioners' delta hedging lags significantly behind." (François, Gauthier, Godin & Pérez-Mendoza 2025, *Enhancing Deep Hedging … IV Surface Feedback*, p. 29, printed p. 28)

  That backtest used real prices:
  > "Backtests are conducted on 4,134 around-the-money call options, using actual market prices observed between December 31, 2020 and October 31, 2023." (same, p. 29, printed p. 28)

### 3. Forecasting: plain GARCH misses it
- > "The original GARCH model tends to perform well with exchange rate data, but it is typically outperformed by models that can accommodate a leverage effect when applied to equity returns" (Hansen, Huang, Tong & Wang 2021, *Realized GARCH, CBOE VIX, and the VRP*, p. 12)

### 4. The VRP: the market prices in more leverage than actually happens, but the papers disagree on how much of the premium it explains
- **Option prices imply a stronger leverage effect than realized data shows:**
  > "a stronger (more negative) leverage correlation under Q than under P." (Hansen et al., p. 3)

  Q is the risk-neutral world (option prices); P is the real world. This gap is one source of the steep put skew.
- **Hansen et al. attribute only a small part of the VRP to it:**
  > "This suggests that the majority of VRP is due to compensation for the volatility shock, ut, and only a small of fraction of the VRP can be attributed to the leverage effect and the equity premium." (Hansen et al., p. 18)

  They flag that this depends on their model:
  > "This finding is specific to the RG model structure, that only includes a short-term leverage effect." (Hansen et al., p. 18)
- **Cheng, Renault & Sangrey push the other way:**
  > "most of the signal in the risk premia comes from the covariance of the returns with the variance." (Cheng et al., p. 37, printed p. 36)

  They also warn that the VRP mixes two different risks together:
  > "the presence of a leverage effect implies that the variance risk premium does not separately identify the risk aversion to volatility of volatility and the standard risk aversion to volatility level." (Cheng et al., p. 37, printed p. 36)

### 5. Why this makes short gamma painful in selloffs
- Sepp, discussing the option seller's side:
  > "losses (especially for equity index options) will inevitably occur at bad times during market declines and risk-aversion periods." (Sepp 2013, *When You Hedge Discretely*, p. 3)

## How the papers connect

| Paper | Builds on / agrees with | Differs from | Key contribution |
|---|---|---|---|
| Chong & Todorov 2024 | Black 1976; Aït-Sahalia, Fan & Li | Uses options, not returns, to measure it | Leverage effect spikes in stress; vol-of-vol fairly stable; Heston doesn't fit |
| Cheng, Renault & Sangrey 2024 | Bandi & Renò 2016 | Hansen et al. on what drives the VRP | Leverage effect is hard to measure; VRP mixes two risks |
| Hansen et al. 2021 | EGARCH-type models | Cheng et al. | Leverage stronger under Q than P; leverage models beat plain GARCH |
| Ruf & Wang | Hull & White 2017; Black 1976 | Neural network hedging papers | Simple leverage-adjusted delta regressions work as well as neural networks |
| François et al. 2025 (IV feedback) | Bates 2005 (smile-implied delta) | Plain delta hedging | Smile-aware deltas keep up with RL; plain delta lags |
| Sepp 2013 | — | — | Short options lose in bad times |

- **Agreement on hedging.** Ruf & Wang, François et al. and Hull & White (web) all find that a delta which accounts for how IV moves with spot beats the plain delta on S&P 500 options, and that simple versions are enough.
- **Agreement on forecasting.** Hansen et al. favor leverage-aware models for equity volatility. Corsi & Renò (web) extend HAR in the same direction.
- **Disagreement on the VRP.** Hansen et al. put only 2.2% of the log-VRP on the leverage/equity term in their model. Cheng et al. find most of the risk-premium signal comes from the return-variance covariance. Both caution that their answer depends on how the model is set up.

## Relevance to the LS Gamma desk
These are suggestions, not decisions the desk has made:
- **Hedging (`Algos/Hedging/`).** `delta_hedge.py` hedges to IBKR's model delta. If that delta holds IV fixed as SPY moves (worth checking), the papers say it's biased for SPY options:
  - **Long straddle or strangle:** delta-hedged to zero, it still gains when SPY falls, because IV rises and the position is long vega. In effect it carries a hidden short-SPY position.
  - **Short straddle, strangle or iron condor:** the reverse. It carries a hidden long-SPY position, so a selloff hurts through both gamma and vega at once.

  A candidate new hedger is a minimum-variance delta hedger: target shares from delta plus a vega adjustment (Ruf & Wang's $\delta = a\,\delta_{BS} + b\,V_{BS}$, or the Hull–White form), with the coefficients fitted on history. The pipeline already saves vega in the chain, and daily ATM IV and VIX to estimate the spot-vol relationship. The `new-hedger` skill fits this.
- **Forecasting (`forecasting/`).** `GARCH.py` is symmetric GARCH(1,1). Candidates are GJR-GARCH (the same `arch` library with `o=1`), EGARCH, or a leverage-aware HAR (LHAR, which adds lagged negative returns). The `new-forecaster` skill fits this.
- **Regime features (`pipeline/`).** Suggested additions:
  - a rolling correlation between SPY returns and VIX changes, as a direct leverage-effect gauge
  - keeping VVIX as a separate input, since Chong & Todorov find vol-of-vol behaves differently from vol level

  The pipeline already collects SPY, VIX and VVIX.
- **Structure choice.** Because volatility rises in selloffs, the downside is where short-gamma structures take the most damage. Defined-risk structures (iron condor) or the put side's size deserve attention when the leverage effect is strong. That's an inference from the papers, not a tested result.

## Gaps and open questions
- **No paper tests leverage-adjusted hedging on a gamma scalping P&L.** Ruf & Wang and Hull & White minimize one-day hedging error on single options. A minimum-variance delta may reduce P&L noise but could change how much gamma P&L you capture. That needs a backtest.
- **Estimation noise.** Cheng et al. say the effect is hard to measure from returns, and Chong & Todorov needed intraday option data. The desk's live pipeline is daily, so a daily spot-vol slope will be noisy.
- **SPX vs SPY.** Most evidence uses SPX or S&P 500 index options. SPY options are American-style and pay dividends. The differences are probably small, but they haven't been tested here.
- **Time variation.** The effect is strongest exactly when vol spikes (Chong & Todorov), so fixed-coefficient hedges and forecasts may be too weak in a crisis.
- **The VRP split is unresolved.** How much of the VRP pays for leverage/crash risk versus pure vol risk depends on the model (Hansen et al. vs Cheng et al.).

## Sources
**Repo papers used, with pages cited:**
- `2305.04137v2.pdf`: Chong & Todorov, *Volatility of Volatility and Leverage Effect from Options* (pp. 1, 18, 19, 20)
- `24-013 PIER Paper Submission.pdf`: Cheng, Renault & Sangrey, *Identifying the Volatility Risk Price Through the Leverage Effect* (pp. 4, 37)
- `Hedging-with-Linear-Regressions-and-Neural-Networks.pdf`: Ruf & Wang (pp. 2, 10, 11)
- `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`: Hansen, Huang, Tong & Wang (pp. 3, 12, 18)
- `Enhancing-Deep-Hedging-of-Options-with-Implied-Volatility-Surface-Feedback-Information.pdf`: François et al. (p. 29)
- `When-You-Hedge-Discretely-Optimization-of-Sharpe-Ratio-for-Delta-Hedging-Strategy-under-Discrete-Hedging-and-Transaction-Costs.pdf`: Sepp (p. 3)

**Checked, only passing mentions or none:**
- `Is-the-Difference-between-Deep-Hedging-and-Delta-Hedging-a-Statistical-Arbitrage?.pdf`: its GARCH simulator includes a leverage effect; not analyzed
- `Deep-Hedging-with-Options-Using-the-Implied-Volatility-Surface.pdf`: uses the IV surface, but no leverage-effect discussion
- `PRISM-…pdf`: discusses SPX put skew from regime switches, not the leverage effect as such
- Nothing relevant (hits were "leverages" in the ordinary sense or position-size limits): the other deep hedging and RL papers, the RV-forecasting papers, OPHR

**Web sources (outside the repo):**
- [Hull & White 2017, *Optimal Delta Hedging for Options* (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2658343) and the [OptionMetrics summary](https://optionmetrics.com/research/hull_white_2017/). The abstract says the minimum-variance delta accounts for "the expected change in volatility conditional on a price change". I couldn't access the full text to confirm its reported error reductions, so none are quoted here.
- [Corsi & Renò 2012, *Discrete-Time Volatility Forecasting with Persistent Leverage Effect* (JBES)](https://www.tandfonline.com/doi/full/10.1080/07350015.2012.663261), [open-access PDF](https://openaccess.city.ac.uk/id/eprint/4434/1/CorsiReno_LHAR_sub2012.pdf)
- [Aït-Sahalia, Fan & Li 2013, *The Leverage Effect Puzzle* (JFE)](https://ideas.repec.org/a/eee/jfinec/v109y2013i1p224-249.html)

**Suggested papers to add to `docs/papers/`:**
1. **Hull & White 2017:** the minimum-variance delta, the most direct upgrade to `delta_hedge.py`.
2. **Corsi & Renò 2012 (LHAR):** a leverage-aware HAR, the natural next model after GARCH.
3. **Aït-Sahalia, Fan & Li 2013:** why the effect is hard to measure; useful before trusting any daily estimate.
4. **Bates 2005 (smile-implied delta):** the benchmark delta used by François et al. Found only through their citation, not on the web.
