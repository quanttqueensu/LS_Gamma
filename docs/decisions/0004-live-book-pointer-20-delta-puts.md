# 0004. Trade the stress-sized 20-delta put book live, through a one-line book pointer
*Date: 2026-11-12 · Status: Accepted*

**Context:** Since October the paper account has traded the VRP band (short or long at-the-money gamma, 1 contract), which loses money in the backtest (−$2,060 / −$4,122 at 1x / 2x, 2014-06 to 2024-12). The always-short, stress-sized put books passed their pre-registered bars in-sample (2026-10-22 stress-sized-puts, 2026-11-02 lower-delta). Since 26 September every idea has also run as a shadow book on the live snapshots, so the desk can switch to one without losing sight of the others.

**Decision:**
- **Pointer:** `configs/paper.toml` gets `[strategy] book = "2026-11-02-lower-delta/put20"`. The live runner then trades exactly that book's merged config (paper.toml + backtest.toml + the variant): always short, the put nearest 20 delta, sized so a one-day 20% SPY drop with IV at max(60%, IV) costs at most 35% of $250k, hedged in 10-share steps. Deleting the line switches back.
- **Previous rules stay in shadow:** the rest of `paper.toml` is unchanged. It remains the research baseline and runs as the "VRP band (paper.toml)" shadow book.
- **Same code live and in backtests:** the strike-by-delta and stress-sizing rules moved to `trading.sizing` and are shared by the engine and the runner (parity test on this book).
- **Guard:** the runner refuses, before connecting, any book that sets a backtest research flag it does not implement.
- **Partial fills:** a multi-contract order records the filled quantity; a partial close keeps the rest open.

**Evidence:**
- In-sample (2014-06-02 to 2024-12-31), at 1x / 2x spreads:

  | | put20 | 25-delta stress book | VRP band (baseline) |
  |---|---|---|---|
  | Net P&L | +$149,893 / +$133,123 | +$121,482 / +$101,172 | −$2,060 / −$4,122 |
  | Sharpe | 0.78 / 0.69 | 0.52 / 0.43 | −0.36 / −0.68 |
  | Max drawdown | $48,435 / $51,352 | $70,362 / $75,488 | $3,027 / $4,258 |
  | ES 5% (daily) | −$2,457 / −$2,489 | −$3,016 / −$3,094 | −$97 / −$105 |

- $26.5k of put20's $28.4k lead over the 25-delta book comes from August 2015 (lower-delta summary).
- **Out of sample (2025-01-01 to 2026-07-10) has not been run** for either book. The case is in-sample only.
- Shadow books, 26 September to 10 November (23 snapshot days): put20 +$3,211, the 25-delta book +$3,405, the VRP band −$107. That is too short to compare.

**Consequences:**
- The book is about 9 contracts at today's prices and more after a selloff; initial Reg T margin is about $170k of the $250k (puts plus the share hedge). Check buying power before the first run.
- The first run closes the open long call (reason "flip"), sells the sized put and hedges to about −170 to −180 shares.
- `[size] capital` now sizes positions.
- Future promotions are the same one-line pointer to a shadow book, after the decision record.
