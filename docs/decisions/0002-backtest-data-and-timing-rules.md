# 0002. Backtest data and timing rules
*Date: 2026-10-15 · Status: Accepted*

**Context:** The backtest replays R2 SPY option trades into the same snapshots the live pipeline saves. Every rule below either blocks look-ahead or keeps the backtest from being more optimistic than live.

**Decision:**
- **Timing:** decide on data up to 15 min before the decision time (paper IBKR data is 15 min delayed); fill on trades in the 15 min after it. Snapshot grid every 30 min, 10:15 to 15:45 ET. Stops are checked at every scheduled run.
- **Window:** 2014-06 to 2026-07-10, never later (R2 ends there; no other source is used to extend it). Hold-out 2025-01-01 to 2026-07-10.
- **Daily data:** forecasts use completed days only (up to yesterday's close), live and backtest. SPY daily from CRSP; 2026 closes from R2 put-call parity. VIX from CBOE, rf from Fama-French; VIX9D, VIX3M and VVIX from a one-time frozen yfinance download.
- **Costs:** bid/ask from a spread model fit on live IBKR quotes, run at 1× and 2× (`spread_mult`). It fits the mean cost (least squares) per delta tier (≤0.8, 0.8–0.9, >0.9), because expected P&L needs expected cost. Commissions $0.65 per contract and $0.005 per share, with a $1 minimum per order (0003).
- **Ownership:** Claude builds the replay pipeline and engine; analysts use them.

**Evidence:**
- R2 has trades but no quotes and no intraday SPY. Near-ATM put-call pairs within 5 s give a consistent forward (2024-06-12: 543.3 to 543.8 across six strikes).
- 30-DTE strikes trade only a few times per 15 min, so marks come from a smile fit across strikes.
- Live quotes span only about 2 weeks of calm markets, so the 2× spread run is required.
- Report: research/strategy_research/2026-10-01-walk-forward-backtest-without-look-ahead.pdf.

**Consequences:**
- The live runner now fits on completed days, a slight change to live forecasts.
- Each 2026 ex-dividend day's return is off by about 0.25%.
- A result that only passes at 1× spreads does not pass.
