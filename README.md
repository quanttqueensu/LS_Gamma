# Long/Short Gamma desk, QUANTT
**Regime-dependent gamma scalping on SPY options**

---

## Repo Layout

```
src/lsgamma/
├── core/Algos/            # IBKR trade execution only (paper trading)
│   ├── broker.py          # connection (paper-only guard) + order submission
│   ├── LG_*/              # long gamma structures (5)
│   ├── SG_*/              # short gamma structures (5)
│   └── Hedging/           # hedging policies (delta hedge)
├── pipeline/              # daily data snapshot: yfinance + IBKR option chain
├── forecasting/           # RV forecasters: GARCH, HAR
├── signals/               # signal models: VRP band
├── trading/               # contract selection, exits, P&L, ledger, daily runner, smoke test
├── experiments.py         # research run logger (results/research/)
└── backtest/              # (not built yet)
research/                  # Research notes (AI), papers (Written by Analysts or PM), etc.
├── README.md              # how research works: workflow, rules, path to live
├── _template/             # copy to start an experiment (hypothesis card, script, summary)
├── Agentic_Routing/       # topic sandboxes: README (who's on it, experiments) + one folder per hypothesis
├── Deep_Hedging/
├── RV_Forecasting/
├── strategy_research/     # research reports (LaTeX + PDF)
└── Misc_Research_Notes/   # deep research reports and notes (LaTeX + PDF)
docs/
├── education/             # 10 onboarding lessons (LaTeX + PDF)
├── decisions/             # decision records
├── papers/                # research papers (Academic)
├── scripts.md             # how to test and run everything
└── repo-architecture.png  # architecture diagram
configs/
├── paper.toml             # every strategy number for paper trading
└── experiments/           # one TOML per research experiment (+ TEMPLATE.toml)
tests/                     # offline tests (pytest, fake IBKR)
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
**Portfolio Manager: Gabriel Soler**

#

*R&D: Ben Gorenc*

#

*Analysts: Brandon Scheidler, Elizabeth Bighiu, Zach Glazer*
