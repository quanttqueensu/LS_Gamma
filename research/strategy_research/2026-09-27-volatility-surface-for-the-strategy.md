# Should the Desk Build a Volatility Surface?
*Strategy research · 2026-09-27 · L/S Gamma Desk, QUANTT*

**Question:** would a volatility surface make sense to create for our strategy?

**Method:** Searched all 22 papers in `docs/papers/` (page-tagged index) + web search.
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Related research:** [Leverage effect and the desk](2026-09-27-leverage-effect-and-the-ls-gamma-desk.md) (surface-based deltas) · [Deep hedging as the P&L driver](2026-09-27-deep-hedging-as-gamma-scalping-pnl-driver.md)

---

## Short answer
Yes, but in two stages, and the first stage is small.

**Stage 1 (useful now): a surface *summary*.** A handful of numbers pulled from the daily IBKR chain the pipeline already collects:
- ATM implied vol at a couple of tenors (days to expiry), e.g. 30 and 60 days
- the term-structure slope between them
- 25-delta put and call IV, and the skew between them

This is what the papers actually feed their models. It gives the VRP signal an implied vol at the tenor you trade, instead of VIX (which is SPX, fixed at 30 days), and it adds regime and structure-choice inputs.

**Stage 2 (only when needed): a full fitted surface,** meaning IV for any strike and expiry. It's needed for pricing options in backtests, for surface-based deltas, and for deep hedging research, but not for choosing today's trade.

The strongest evidence in the library: surface information clearly improves RL hedging. The surface's **level and term slope** matter most, and the **smile shape** is second-order, except for short-dated options when the focus is tail risk.

## What the papers say

### 1. Which parts of the surface matter
- **One compact way to describe a whole surface is five numbers:**
  > "the long-term at-the-money (ATM) level, the time-to-maturity slope, the moneyness slope, the smile attenuation and the smirk, respectively" (François, Gauthier, Godin & Pérez-Mendoza 2025, *Enhancing Deep Hedging … IV Surface Feedback*, p. 10, printed p. 9)

  "Smile attenuation" is how quickly the smile flattens as expiry lengthens; "smirk" is the extra steepness on the downside (put) side.
- **Level and term slope drive hedging decisions:**
  > "Overall, the conditional variance of the underlying asset returns, the long-term ATM level β1 and the time-to-maturity slope β2 of the IV surface play a major role, no matter what risk measure or moneyness is considered." (same, p. 26, printed p. 25)

  > "The moneyness slope, the smile attenuation and the smirk have a second order effect." (same, p. 26, printed p. 25)
- **Except for short-dated tail risk,** which is relevant because the desk trades 1–60 DTE:
  > "high values of the smile attenuation (β4) and the smirk (β5) indicate a steep slope and a strong smirk for the short term smile which, in turn, induces a high exposure to tail risk for short term options." (same, p. 26, printed p. 25)

### 2. Surface information improves results, but only as an input to a good method
- **Their conclusion:**
  > "Out-of-sample backtests underscore the critical role of IV surface information in unlocking the full potential of RL-based hedging strategies." (François et al. 2025, *Enhancing…*, p. 31, printed p. 30)
- **On hedging straddles:**
  > "The main conclusion is that RL approaches do not necessarily dominate traditional methods; their performance critically depends on the information provided to the algorithm." (François et al. 2025, *Deep Hedging with Options Using the IV Surface*, p. 29, printed p. 28)

  > "receiving information about the IV surface clearly improves the performance the RL algorithm." (same, p. 29, printed p. 28)
- **The surface also carries the VRP:**
  > "but also capture the current price levels for options (and the associated variance risk premium) within rebalancing decisions." (same, p. 33, printed p. 32)
- **A full surface is needed to price and mark positions.** In their setup the straddle's value:
  > "is determined using the IV surface prevailing at that moment." (same, p. 12, printed p. 11)

### 3. What a practical SPY setup actually uses: a summary, not a full surface
- **Their features:**
  > "at–the–money (ATM) implied volatility at 30d and 91d horizons; term-structure slope (iv_91d - iv_30d); 25-delta put/call and skew; VIX and the 10-year Treasury yield; and realized/historical volatilities" (*Deep Hedging with RL: A Practical Framework*, p. 3)
- **Why it's worth tracking:**
  > "term structure and skew swing within weeks" (same, p. 2)
- **The data-quality catch:**
  > "Deep out-of-the-money (OTM) strikes frequently drop observations, forcing strict quality filters and guarded forward-fills before features become usable." (same, p. 2)

### 4. Surface shape as a trading signal
- **PRISM watches the surface constantly:**
  > "The VRC derivatives desk monitors the SPX implied volatility surface in real time" (Verma 2026, *PRISM*, p. 28)

  It also claims skew predicts stress. This is the firm's own observation, not tested evidence, since PRISM is a non-peer-reviewed whitepaper:
  > "consistent with VRC's observation that SPX skew steepens in the 2–3 weeks before elevated-volatility episodes." (*PRISM*, p. 28)
- **OPHR names smile and term structure as its next opportunities:**
  > "Future work could explore additional volatility trading opportunities, such as volatility smile skewness and term structure anomalies" (*OPHR*, p. 10)

### 5. How the surface moves with spot (links to the leverage-effect report)
- > "Cont and Da Fonseca [2002] claim that the leverage effect is due to a shift in the overall level of the implied volatility surface and not due to relative movements, that is, changes in the shape of the implied volatility surface." (Ruf & Wang, *Hedging with Linear Regressions and Neural Networks*, p. 8)

  This supports tracking the surface *level* closely, and its shape less often.

## How the papers connect

| Paper | Builds on / agrees with | Differs from | Key contribution |
|---|---|---|---|
| François et al. 2025, *Enhancing…* | François et al. 2022 (five-factor surface, web); Bates 2005 | Hedges with the underlying only | Level and term slope matter most; smile shape matters for short-dated tails |
| François et al. 2025, *…with Options Using the IV Surface* | *Enhancing…*; Buehler | Hedges with options too, which requires pricing them off the surface | Surface info improves RL; carries the VRP |
| *Practical Framework* (SPY) | Buehler | A handful of summary features, not a full surface | ATM at 30d/91d, term slope, 25Δ skew; warns about wing data quality |
| PRISM | — | Not peer-reviewed | Monitors the surface; claims skew leads vol spikes |
| Ruf & Wang | Cont & Da Fonseca | — | The surface's level moves with spot; its shape moves less |
| OPHR | — | — | Smile and term structure named as untapped signals |

- **Agreement:** every paper that uses surface information reduces it to a few factors, either five parametric ones or ATM/slope/skew summaries. None feeds a raw grid of IVs into a decision.
- **Ranking:** level and term slope first, smile shape second (François et al.), with the exception of short-dated tail risk.
- **A full fitted surface appears only where options must be *priced*:** marking a position, or hedging with options.

## Relevance to the LS Gamma desk
These are suggestions, not decisions the desk has made:
- **What already exists:**
  - The live pipeline's IBKR `chain` has per-contract IV and delta for Friday expiries, 1–60 DTE, strikes within ±10%, and `atm_iv` per expiry. That's already the raw material for Stage 1.
  - The desk's v1 code (branch `archive/v1-ls-gamma`) built fuller surfaces from R2 trade data (`surface/smile_params`, `term_structure`, a smile-based pricer in `marks.py`). That code can be reused for Stage 2 in backtesting.
- **Stage 1: surface summary features** (a small addition to `pipeline/features.py`):
  - ATM IV interpolated to fixed tenors (e.g. 30 and 60 DTE; you set the tenors)
  - the term slope between them
  - 25-delta put IV, 25-delta call IV, and the skew (put minus call)
  - optionally a put-wing measure for the short-gamma structures

  Uses:
  1. **VRP at the traded tenor:** IV at the structure's DTE minus the RV forecast, rather than VIX.
  2. **Regime features** for the router, alongside the VIX term-structure ratios already collected.
  3. **Structure choice:** e.g. whether puts are rich relative to calls when choosing a strangle, a straddle or an iron condor.
- **Stage 2: a fitted surface, when a project needs it:**
  - backtesting on R2 data, which has trades but no quotes, so every strike must be priced from a fitted smile
  - smile-implied or minimum-variance deltas (see the leverage report)
  - deep hedging state and simulation

  Standard choices are SVI per expiry, fitted so it can't produce arbitrage (Gatheral & Jacquier, web), or the five-factor model the François et al. papers use (web).
- **Not recommended:** building a full surface only to pick today's trade. The evidence says the summary numbers carry most of the useful information.

## Gaps and open questions
- **No paper tests surface features as a *signal* for choosing long vs short gamma.** The evidence is about hedging. OPHR lists it as future work, and PRISM's skew claim isn't independently tested.
- **Delayed, gappy wing data.** IBKR's free data is about 15 minutes delayed, and far out-of-the-money strikes can be missing. The *Practical Framework* warns about this (p. 2). The pipeline's ±10% strike range and Friday-only expiries may limit how well the far put wing is measured.
- **SPX vs SPY.** The five-factor model was fitted to S&P 500 index options. Whether its factors carry over cleanly to SPY options is untested here.
- **Fitting risk.** A badly fitted surface can quote prices that allow arbitrage. That's why a Stage 2 surface should use a constrained method like arbitrage-free SVI.
- **Which tenors?** The papers use 30/91 days or 21/63/126 days. The desk's tenors should match the DTEs it actually trades, which is the PM's call.

## Sources
**Repo papers used, with pages cited:**
- `Enhancing-Deep-Hedging-of-Options-with-Implied-Volatility-Surface-Feedback-Information.pdf`: François, Gauthier, Godin & Pérez-Mendoza (pp. 10, 26, 31)
- `Deep-Hedging-with-Options-Using-the-Implied-Volatility-Surface.pdf`: François et al. (pp. 12, 29, 33)
- `Deep-Hedging-with-Reinforcement-Learning-A-Practical-Framework-for-Option-Risk-Management.pdf` (pp. 2, 3)
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf`: Verma (p. 28)
- `Hedging-with-Linear-Regressions-and-Neural-Networks.pdf`: Ruf & Wang (p. 8)
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf` (p. 10)

**Checked, only passing mentions or none:**
- `Deep-Hedging-Learning-to-Simulate-Equity-Option-Markets.pdf`: simulates option markets from a compressed surface representation; relevant only if the desk builds a simulator
- `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`: "skew" there means return skewness, not the IV smile
- `Agents-Are-not-Algorithms.pdf`, the other deep hedging and RL papers, and the RV-forecasting papers: no surface discussion

**Web sources (outside the repo):**
- [Gatheral & Jacquier 2014, *Arbitrage-free SVI volatility surfaces* (Quantitative Finance)](https://www.tandfonline.com/doi/abs/10.1080/14697688.2013.819986), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2033323), [reference code](https://github.com/JackJacquier/SSVI)
- [François, Galarneau-Vincent, Gauthier & Godin 2022, *Venturing into Uncharted Territory: An Extensible Implied Volatility Surface Model* (J. Futures Markets)](https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.22364), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3888243)
- [François et al. 2026, *Joint Dynamics for the Underlying Asset and Its IV Surface* (J. Futures Markets)](https://onlinelibrary.wiley.com/doi/10.1002/fut.70068)

**Suggested papers to add to `docs/papers/`:**
1. **Gatheral & Jacquier 2014:** the standard way to fit an arbitrage-free smile per expiry; the likely Stage 2 method.
2. **François et al. 2022:** the five-factor surface model behind both deep hedging papers; the factors are directly interpretable as features.
3. **François et al. 2026 (joint dynamics):** how spot and the surface move together; useful for simulation and deep hedging.
4. **Cont & Da Fonseca 2002, *Dynamics of implied volatility surfaces*:** the classic study of how surfaces move. Found only through Ruf & Wang's citation, not on the web.
