# 0003. Stop cool-off and $1 commission minimum
*Date: 2026-10-15 · Status: Accepted*

**Context:** After a stop, live and backtest re-entered the same side in the same run whenever the signal still said so. This caused four stop-and-re-enter cycles in March 2020. Separately, the backtest charged $0.65 per contract and $0.005 per share with no per-order minimum, which understates the cost of frequent small hedges.

**Decision:**
- **Cool-off:** after a stop, no new entry on the same side until the next trading day (`[exit] stop_cooloff_days = 1`, live and backtest). Opposite-side entries are not blocked.
- **Commission minimum:** the backtest charges at least $1.00 per order (`[backtest] min_per_order`), as IBKR Pro Fixed does.

**Evidence:**
- Kaminski & Lo (2014) treat a stop as a pair: an exit rule plus a separate re-entry rule. Re-entering at once mostly undoes the stop and pays the spread twice.
- Volatility clusters after big moves, and during crashes the VRP signal often stays short.
- The 2026-10-07 experiments put the desk's tail risk in a few crash windows.
- No study tests this exact rule for daily-hedged SPY options, so 1 day is a reasoned default, not a fitted value.

**Consequences:** The length of the cool-off is tested as a pre-registered backtest experiment on the development window only, with a hypothesis card written before running: none vs 1 day vs 5 days vs waiting for a signal reset, judged on ES and total P&L at 1× and 2× spreads.
