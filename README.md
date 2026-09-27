# QUANTT 2026 - Long/Short Gamma desk
**Regime-dependent gamma scalping on SPY options**

The RV forecast gives the signal, and market regime data picks which algo to run.

---

## Repo Layout

```
src/lsgamma/
├── core/Algos/        # IBKR trade execution (paper trading)
│   ├── broker.py      # connection + order submission
│   ├── LG_*/          # long gamma structures
│   ├── SG_*/          # short gamma structures
│   └── Hedging/       # hedging policies (delta hedge)
├── forecasting/
└── backtest/
research/              # sandbox notebooks by topic
docs/
├── education/         # team learning material
├── decisions/         # decision records
└── papers/            # research papers
configs/
tests/
```

---

## Research Topics

- Agentic Routing
- Deep Hedging
- RV Forecasting

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

## Setup

```bash
git clone https://github.com/quanttqueensu/LS_Gamma.git
cd LS_Gamma
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```



---

*QUANTT — Queen's University Algorithmic Network and Trading Team*
------
*PM: Gabriel Soler*

*Members: TBD*
