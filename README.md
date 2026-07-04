# QUANTT 2026 - Long/Short Gamma desk
**Regime-dependent gamma scalping on SPY options**


[View Architecture](https://miro.com/app/board/uXjVHSQDo3w=/?share_link_id=797835084657)

## Overview

A systematic options strategy that exploits the **Volatility Risk Premium (VRP)**, the tendency for implied volatility to exceed realized volatility (~70-80% of the time). The strategy switches between two regimes based on RV forecasts.

| Regime | Condition | Position | Edge |
|--------|-----------|----------|------|
| **Short Gamma** | IV overpriced | OTM Strangle | Collect VRP, delta-hedge losses |
| **Long Gamma** | IV underpriced | ATM Straddle | Gamma scalp exceeds VRP cost |

Delta is re-hedged hourly. Volatility forecasts run daily to determine regime.

---

## Strategy Logic

1. **Forecast realized volatility** using models developed in-house (alongside public models: HAR, GARCH, etc.)
2. **Compare to implied volatility** (derived via reverse Black-Scholes)
3. **Enter position** based on VRP signal:
   - Short gamma → sell OTM strangle (~5% OTM), collect premium upfront
   - Long gamma → buy ATM straddle, profit from gamma scalping
4. **Re-hedge delta** by buying/selling SPY shares as delta drifts from zero
5. **Exit** no later than 3 DTE (entry window: 7-28 DTE)

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Sharpe | > 1.2 |
| Sortino | > 1.5 |
| Max Drawdown | < 15% |
| Hit Rate | > 53% |
| VRP Capture | > 60% of theoretical VRP |

Benchmarks: CBOE VIX short-term futures index, SPY buy-and-hold

---

## Risk Management

**Long gamma** — VRP hard stop, realized vol trailing check, 5-10% position size cap  
**Short gamma** — 30% premium hard stop, wider re-hedge threshold, 20% short-side budget cap

---

## Data Sources

- Bloomberg, yFinance, Alpaca API, WRDS/OptionMetrics
- SPY prices (1-5 min), SPY options chain (EOD Greeks + IV), VIX, risk-free rate

---

## Setup

```bash
git clone https://github.com/Gabe-Soler/LS_gamma.git
cd LS_gamma
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

*QUANTT — Queen's University Algorithmic Network and Trading Team*
------
*PM: Gabe Soler*

*Members: TBD*