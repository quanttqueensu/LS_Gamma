# 0005. Size the live book to the real account and check margin before entry
*Date: 2026-11-16 · Status: Accepted*

**Context:** On 2026-11-16 the scheduled run (VM, 11:00 ET) closed the long call and tried to sell 9 puts for the 20-delta put book. IBKR rejected the order (error 201, insufficient margin): it needed 274,637 CAD of initial margin against 258,845 CAD of equity. Two reasons:
- The paper account is in CAD, about 251k CAD (about US$175k at CAD/USD 0.699), while `[size] capital` sized the book for US$250k.
- The 0004 estimate of about US$170k initial margin for 9 puts was low.

The book ended flat, and the ledger matched IBKR.

**Decision:**
- **Live account size:** `[strategy] capital = 175000` in `configs/paper.toml`. It replaces `[size] capital` for the live run only. Backtests, registered baselines and shadow books keep $250k, because `[strategy]` is stripped from research configs. At today's prices that is 6 puts instead of 9. Update it by hand if the account or the exchange rate moves a lot.
- **Pre-trade margin check:** `[strategy] max_margin = 0.8`. Before an entry, the runner asks IBKR for a what-if preview of the option order and of the share hedge it will need (no order is sent). It sizes down until the initial margin after both is at most 80% of equity with loan. The remaining 20% is cushion for a SPY drop. If not even one contract fits, or IBKR returns no preview, it skips the entry and says so.

**Consequences:**
- The live book is a scaled-down version of the put20 shadow book (about 0.7x and fewer contracts). Compare live and shadow P&L per contract.
- The live book can hold fewer contracts than the stress budget allows when margin is tight. The run log prints `margin xN: <after> of <equity> equity (<share>, cap 80%)` each time it enters.
- Exits and hedges are not margin-checked, because they reduce risk.
