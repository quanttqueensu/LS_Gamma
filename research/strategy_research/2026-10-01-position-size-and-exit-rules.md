# Position Size and Exit Rules for Single-Leg Delta-Hedged SPY Options
*Strategy research · 2026-10-01 · L/S Gamma Desk, QUANTT*

**Question:** for the size and exit rules lets also run a /strategy-research on this

**Method:** Searched all 27 papers in `docs/papers/` (page-tagged index) + web search + the desk's v1 rules (`archive/v1-ls-gamma` README).
Quotes verified against the cited PDF pages. Page numbers are PDF pages; printed page
numbers are given where they differ.

**Related research:** [Target DTE, moneyness, calls vs puts](2026-10-01-target-dte-moneyness-calls-vs-puts.md) · [Signal generation](2026-09-29-signal-generation-for-market-state.md)

**Desk decisions already made (PM, 2026-10-01):** v1 VRP band; single-leg calls and puts; daily delta hedging.

---

## Short answer
The papers agree on **four kinds of exit**:
1. **Time:** get out before the final week.
2. **Signal reversal:** the thesis is gone.
3. **Loss limit:** a hard risk stop.
4. **Profit take:** optional.

For **size**, the serious frameworks either cap a risk measure (vega, max loss, collateral) or use a fraction of Kelly. Kelly needs P&L statistics the desk doesn't have yet.

For paper trading, the simplest sound start is **1 contract per trade** with time, signal and loss exits. Scale up only once real P&L data exists.

## What the papers say

### 1. Time exits: avoid the final week
- **PRISM rolls before the last week:**
  > "VRC rolls all options positions when time to expiry falls below 5 trading days." (Verma 2026, *PRISM*, p. 36)

  The reason given is that it:
  > "avoids the theta cliff of the final week" (*PRISM*, p. 36)
- **v1 desk rule:** enter at 7–28 DTE and exit no later than 3 DTE (v1 README).
- **The Cboe PutWrite benchmark is the opposite extreme:** it sells 1-month ATM puts monthly and **holds them to expiry**, fully collateralized ([Wikipedia](https://en.wikipedia.org/wiki/CBOE_S&P_500_PutWrite_Index), [Cboe methodology](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_SP_500_PutWrite_Indices_Methodology.pdf)). That index isn't delta-hedged, though.

### 2. Signal exits: close when the thesis reverses
- **PRISM's VRP reversal trigger** fires when the VRP z-score stays negative for three consecutive closes. This:
  > "signals that implied vol has fallen below VRC's regime-adjusted realized vol estimate" (*PRISM*, p. 37)
- **OPHR's baselines close and flip:**
  > "If predicted volatility crosses the opposite threshold, the position is closed and reversed." (Chen, Cai, Qin & An, *OPHR*, p. 28)

### 3. Loss and profit limits
- **OPHR's baselines use percentage limits plus a maximum hold:**
  > "the position is closed if the profit reaches p% or if the loss reaches l%. In addition, a maximum holding period" (*OPHR*, p. 26)

  Their settings (take-profit 5%, stop 3%, 96-hour maximum hold, 60–90 day options, p. 27) are tuned for hourly crypto trading and **don't transfer** to daily SPY.
- **v1 desk rules:** for long gamma, a VRP hard stop and a realized-vol trailing check; for short gamma, a stop at 30% of premium.
- **Profit taking at 50% of premium** on short puts is common practitioner advice. I couldn't verify a rigorous study (the one found couldn't be accessed), so treat it as untested.

### 4. Sizing
- **Fractional Kelly:**
  > "VRC applies a fractional Kelly factor of 1/2 as standard policy" (*PRISM*, p. 23)

  Kelly needs the mean and variance of trade P&L, which the desk will only have after paper trading.
- **PRISM's hard limits (p. 38):**
  - net vega at most 3% of assets
  - 99% daily CVaR at most 0.75% of notional
  - delta exposure at most 2× assets
  - exit if ATM bid-ask spreads exceed 100bp of vol
- **The PutWrite index** sizes so that T-bills "can finance the maximum possible loss from final settlement" of the puts sold. That's the most conservative rule.
- **v1 desk caps:** long gamma at 5–10% of capital; a 20% budget for the short side.

## How the papers connect

| Source | Exit approach | Sizing approach |
|---|---|---|
| PRISM (whitepaper) | Roll at under 5 trading days; signal reversal; P&L at 2.5σ below expectation; hard limits | Half-Kelly with an uncertainty penalty; vega, CVaR and leverage caps |
| OPHR baselines | Take-profit, stop-loss, max hold; close and reverse on opposite signal | By margin use |
| Cboe PutWrite (web) | Hold to expiry | Fully collateralized |
| v1 desk | Exit at 3 DTE; VRP and premium stops | 5–10% long, 20% short budget |

- **Everyone uses a time exit and a thesis exit.** They differ mostly on whether to add profit and loss stops.
- **Sizing goes from simplest (full collateral) to most data-hungry (Kelly).** Risk caps such as vega or max loss sit in between.

## Relevance to the LS Gamma desk
Suggested starting rules for paper trading. These are suggestions; the PM sets the numbers.
1. **Size:** 1 contract per trade. Paper trading is first a mechanics test. Later, size by a vega or max-loss budget, and only consider half-Kelly once there's P&L history.
2. **Time exit:** close at about 7 calendar DTE, which is roughly PRISM's 5 trading days.
3. **Signal exit:** close when the signal is back to flat for 3 consecutive days. Close and flip on an opposite signal.
4. **Loss stop:**
   - short put: when the position loss reaches 1–2× the premium received
   - long call: at 50% of the premium paid

   Measure losses including the hedge P&L.
5. **Optional profit take:** close short puts at 50% of premium. Untested; consider running it in shadow to compare.
6. **Log every exit and its trigger,** so the rules can be tuned from data.

## Gaps and open questions
- **No paper tests these exits on daily-hedged single SPY options.** The OPHR numbers are crypto; PRISM is simulated; PutWrite is unhedged.
- **Stops and daily hedging interact.** A stop on option P&L alone ignores hedge gains, so P&L should be measured on the combined position.
- **The account's starting capital and risk budget** aren't set yet, and they're needed before scaling past 1 contract.

## Sources
**Repo papers used, with pages cited:**
- `PRISM-A-Probabilistic-Regime-Integrated-Scalping-Model-for-Derivatives-Arbitrage.pdf` (pp. 23, 36, 37, 38)
- `OPHR-Mastering-Volatility-Trading-with-Multi-Agent-Deep-Reinforcement-Learning.pdf` (pp. 26, 27, 28)

**Checked, nothing on sizing or exits:** the deep hedging papers (they size hedges, not positions), the forecasting papers, `Agents-Are-not-Algorithms.pdf`, `2503.21422v1.pdf`, Sepp (hedging frequency, not exits).

**Web sources (outside the repo):**
- [Cboe S&P 500 PutWrite Indices methodology](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_SP_500_PutWrite_Indices_Methodology.pdf)
- [CBOE S&P 500 PutWrite Index (Wikipedia)](https://en.wikipedia.org/wiki/CBOE_S&P_500_PutWrite_Index)
- [Ennis Knupp, *Evaluating the Performance Characteristics of the CBOE S&P 500 PutWrite Index*](https://cdn.cboe.com/resources/education/research_publications/PUTIndexEnnisKnupp.pdf)

**Suggested papers to add to `docs/papers/`:**
1. **Ennis Knupp PUT index evaluation:** a long-run benchmark for a systematic ATM put-selling program.
2. **A rigorous study of profit and loss rules for short index options,** if one can be found. The practitioner claims remain unverified.
