# Target DTE, Moneyness, and Calls vs Puts for Single-Leg Delta-Hedged SPY Options
*Strategy research · 2026-10-01 · L/S Gamma Desk, QUANTT*

**Question:** what target DTE (days to expiry) and moneyness (how far out of the money, delta) should we use for single-leg delta-hedged SPY options in a long/short gamma VRP strategy; and should long gamma use calls or puts and short gamma calls or puts

**Method:** Searched all 27 papers in `docs/papers/` (page-tagged index) + web search + the desk's own IBKR chain snapshot (2026-09-29).
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Related research:** [Volatility surface](2026-09-27-volatility-surface-for-the-strategy.md) · [Leverage effect](2026-09-27-leverage-effect-and-the-ls-gamma-desk.md) · [Size and exit rules](2026-10-01-position-size-and-exit-rules.md)

**Desk decisions already made (PM, 2026-10-01):** VRP band as v1 (long gamma if forecast RV − IV > +5%, short gamma if < −2%, else flat); single-leg calls and puts only to start; daily delta hedging.

---

## Short answer
Enter **at the money (about 50 delta)**, at the **Friday expiry closest to 30 DTE**, within a 21–45 DTE window.

Use **long ATM calls for long gamma** and **short ATM puts for short gamma**:
- **Why ATM:** it carries the most gamma and vega per contract, and it's where S&P delta-hedged option losses, i.e. the VRP, are largest per option.
- **Why ~30 DTE:** Sepp finds the delta-hedged Sharpe ratio peaks at 1–2 month maturities.
- **Why calls for long, puts for short:** once delta-hedged, an ATM call and an ATM put are economically almost identical. The choice is operational. Short puts avoid early assignment around SPY's ex-dividend dates, and long calls avoid paying the put skew.

Selling *out-of-the-money* puts would collect more premium (puts are 3–4 vol points richer), but that's a later variant with more crash risk and less gamma to scalp.

## What the papers say

### 1. Maturity: 1–2 months is the sweet spot
- **Sharpe peaks at 1–2 months:**
  > "We observe that the optimal Sharpe ratio peaks for options with maturities of one and two month and declines as maturity increases because expected transaction costs increase." (Sepp 2013, *When You Hedge Discretely*, p. 17)
- **Short maturities need frequent hedging:**
  > "The optimal re-hedging period increases for longer maturities from as low as hedging once per 3 days for short-term maturities (up to 2 month) to 7-8 days for longer-term maturities (above 2 years)." (Sepp, p. 17)

  So daily hedging is more frequent than Sepp's optimum for 1–2 month options. That's fine, but costs should be watched.
- **Practice converges on about one month:**
  > "at-the-money call options on S&P 500 with maturity of approximately 30 days" (Bracha, Sakowski & Michańków 2025, *DRL for ATM S&P 500 Options Hedging*, p. 6, printed p. 5)

  > "VRC buys the nearest monthly expiry ATM straddle" (Verma 2026, *PRISM*, p. 35)
- **Very short dates dominate volume but behave differently:**
  > "In 2022, more than 60% of the trading volume of S&P 500 index options was in options expiring within 7 calendar days." (Chong & Todorov 2024, *Volatility of Volatility and Leverage Effect from Options*, p. 2)

  There's plenty of liquidity there, but gamma near expiry swings too fast for once-a-day hedging (inference).

### 2. Moneyness: at the money
- **Most gamma and vega per contract:**
  > "At-the-money options are efficient hedging instruments because they have a large gamma and vega compared with similar maturity options that are significantly in- or out-of-the-money." (Cao, Chen, Farghadani, Hull, Poulos, Wang & Yuan 2022, *Gamma and Vega Hedging Using Deep Distributional RL*, p. 3)

  > "Whereas short maturity at-the-money options are most useful for hedging gamma, longer maturity options work better for vega." (same, p. 17)
- **Standard practice in the RL papers:**
  > "the strategy selects the nearest-to-the-money (ATM) straddle within a predefined maturity range as the underlying instrument." (Chen, Cai, Qin & An, *OPHR*, p. 26)
- **The theory fits ATM best:**
  > "Our current framework is best suited to analyzing at-the-money options for which the impact of the skew is limited." (Sepp, p. 19)
- **ATM needs the most hedging:**
  > "Thus, for at-the-money options with high gamma, the rebalancing is expected to be more frequent, while, for out-of-the money options with low gamma, the re-hedging is only applied for big moves in the spot price." (Sepp, p. 8)
- **ATM shorts take jumps hardest:**
  > "We note that a jump leads to a large realized loss in a short option position only if the option is near at-the-money." (Sepp, p. 18)

### 3. Where the VRP is largest (web, Bakshi & Kapadia 2003)
The classic study of delta-hedged S&P 500 options (1988–1995, 14–60 day maturities) finds:
- "the delta-hedged strategy underperforms zero"
- "the documented underperformance is less for options away from the money"
- for ATM calls, the loss "amounts to 8% of the option value"
- the result is robust "to the inclusion of put options"

So **selling ATM collects the most premium per option**, and **buying ATM pays the most**. Long gamma should only be bought when the RV forecast clearly beats IV, which is what the +5% band enforces.

### 4. Calls vs puts
- **Option buyers lose most on puts, especially out of the money.** Sepp cites Broadie, Chernov & Johannes:
  > "the average monthly return (for long position in a put) is −30% for at-the-money puts and −57% for 6% out-of-the-money puts." (Sepp, p. 3)

  These are unhedged long-put returns, but they show where the richest premium sits.
- **The market prices in more crash risk than actually happens:**
  > "a stronger (more negative) leverage correlation under Q than under P." (Hansen, Huang, Tong & Wang 2021, *Realized GARCH, CBOE VIX, and the VRP*, p. 3)

  Q is the risk-neutral world implied by option prices; P is the real world. This gap is why OTM puts carry the skew premium (see the leverage report).
- **After delta hedging, call vs put at the same strike is mostly equivalent** (put-call parity; see `docs/education/Forward_and_reverse_scalping.md`, section 6). The real differences:
  - **Early exercise:** short ITM SPY calls can be assigned before ex-dividend dates.
  - **Skew:** matters for OTM strikes, little at ATM.
  - **Liquidity**, and the initial hedge size, which is about 50 shares per contract at ATM either way.

### 5. The desk's own data (IBKR chain, 2026-09-29, spot 765.05)

| DTE | ATM IV | 25Δ put IV | 25Δ call IV | 25Δ skew | 10Δ put IV | ATM gamma |
|---|---|---|---|---|---|---|
| 17 | 12.6% | 14.8% | 11.4% | 3.3 pts | 17.7% | 0.019 |
| 24 | 12.6% | 14.9% | 11.3% | 3.5 pts | 18.2% | 0.016 |
| 31 | 13.2% | 15.6% | 11.8% | 3.8 pts | 19.4% | 0.014 |
| 38 | 13.4% | 16.1% | 12.1% | 4.1 pts | 19.9% | 0.012 |
| 52 | 13.6% | 16.4% | 12.1% | 4.3 pts | 20.6% | 0.010 |

- The put skew is clear and grows with maturity.
- ATM gamma per contract roughly halves from 17 to 52 DTE.

## How the papers connect

| Source | Agrees with | Key contribution |
|---|---|---|
| Sepp 2013 | Bakshi & Kapadia | Sharpe peaks at 1–2 month maturities; framework suited to ATM |
| Cao et al. 2022 | OPHR, Bracha | ATM gives the most gamma and vega |
| Bakshi & Kapadia 2003 (web) | Sepp, Hansen | Delta-hedged losses (the VRP) are largest at the money |
| Hansen et al. 2021 | Leverage report | Crash risk priced higher than it occurs, which drives put skew |
| OPHR, Bracha, PRISM | each other | Practice: nearest-ATM, about 1-month options |

- **All sources point to ATM and roughly one-month options** for a delta-hedged VRP trade.
- **The only pull away from ATM is the skew premium** in OTM puts. It's richer, but it comes with more crash exposure and less gamma.

## Relevance to the LS Gamma desk
These are suggestions; the PM sets the final numbers:
- **Entry expiry:** the Friday expiry closest to 30 DTE within 21–45 DTE. The pipeline already pulls Friday expiries out to 60 DTE.
- **Strike:** the listed strike closest to spot, which the pipeline's `atm_iv` logic already finds.
- **Long gamma** (forecast RV − IV > +5%): `LG_LongCall`, ATM.
- **Short gamma** (forecast RV − IV < −2%): `SG_ShortPut`, ATM.
- **IV for the signal:** use the ATM IV at the chosen expiry, not VIX, so the signal matches the option actually traded.
- **Later variant:** a short 25-delta put to harvest the skew, once the ATM version is running and measured.

## Gaps and open questions
- **No paper tests single-leg, daily-hedged SPY options** with these exact choices. Bakshi & Kapadia's data is 1988–1995, before weekly and daily expiries existed.
- **Daily hedging vs Sepp's optimum.** Daily is more frequent than his roughly 3-day optimum, so watch commissions.
- **Dividend dates:** check SPY's ex-dividend calendar if short calls are ever used.

## Sources
**Repo papers used, with pages cited:**
- `When-You-Hedge-Discretely-Optimization-of-Sharpe-Ratio-for-Delta-Hedging-Strategy-under-Discrete-Hedging-and-Transaction-Costs.pdf`: Sepp 2013 (pp. 3, 8, 17, 18, 19)
- `Gamma-and-Vega-Hedging-Using-Deep-Distributional-Reinforcement-Learning.pdf`: Cao et al. (pp. 3, 17)
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf` (p. 26)
- `Application-of-Deep-Reinforcement-Learning-to-At-the-Money-S&P-500-Options-Hedging.pdf`: Bracha et al. (p. 6)
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf` (p. 35)
- `2305.04137v2.pdf`: Chong & Todorov (p. 2)
- `Realized-GARCH,-CBOE-VIX,-and-the-Volatility-Risk-Premium.pdf`: Hansen et al. (p. 3)

**Checked, not relevant to DTE/moneyness:** the forecasting papers, the agent and LLM papers, `2503.21422v1.pdf` (an AI-in-quant survey), and the remaining deep hedging papers. They use ATM or about 30-day options without studying the choice.

**Web sources (outside the repo):**
- [Bakshi & Kapadia 2003, *Delta-Hedged Gains and the Negative Market Volatility Risk Premium* (RFS)](https://people.umass.edu/~nkapadia/docs/Bakshi_and_Kapadia_2003_RFS.pdf), [JSTOR](https://www.jstor.org/stable/1262684)

**Suggested papers to add to `docs/papers/`:**
1. **Bakshi & Kapadia 2003:** the core evidence on delta-hedged option returns by moneyness and maturity.
2. **Broadie, Chernov & Johannes 2009, *Understanding Index Option Returns*:** the source of Sepp's put-return figures. Found only through Sepp's citation.
