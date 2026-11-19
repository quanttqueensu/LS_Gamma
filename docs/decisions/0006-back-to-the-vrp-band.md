# 0006. Trade the long/short VRP band again, sized to 75% of equity with a 10-share hedge band
*Date: 2026-11-19 · Status: Accepted (replaces the 20-delta put pointer of 0004)*

**Context:** Since 2026-11-16 the paper account has traded the stress-sized 20-delta put book (0004), sized to about US$175k with a margin cap (0005). The PM decided to go back to the long/short VRP-band signal that traded before the switch.

**Decision:**
- Remove `book = ...` from `[strategy]` in `configs/paper.toml`. The live runner trades the rules in `paper.toml` again: GARCH forecast; short above +2 vol points, long below −5, otherwise flat; ATM call or put.
- **Hedge band:** `[hedge] min_shares` goes from 1 to 10. The book re-hedges only when its delta gap reaches 10 shares, as in `2026-10-16-hedge-band`, which passed in-sample at 1x and 2x (−$1,097 vs −$2,060 at 1x; 469 hedge orders vs 914). That evidence is in-sample only: the out-of-sample run has not been done.
- **Size:** each new position is sized to 75% of the account. With `[strategy] max_margin = 0.75` and `fill_margin = true` (live only), the runner previews one contract with IBKR (option plus its share hedge), takes as many contracts as fit within 75% of equity in initial margin, then confirms that size with a second preview. `[size] quantity = 5` is used only by backtests, shadow books and dry runs. Estimated from Reg T at about US$175k of equity: a short ATM put plus its hedge takes about US$35k per contract (about 3 contracts), and a long ATM call plus its hedge about US$20k (about 6). The run log prints the real numbers.
- Keep `capital = 175000` (live only). `max_margin` goes from 0.8 to 0.75.
- The put20 book keeps running as a shadow book.

**Consequences:**
- The 5 short Dec 18 710 puts opened on 2026-11-16 stay open under the VRP-band exit rules:
  - close at 7 DTE (Dec 11);
  - stop at 1x the total credit;
  - profit take at 50%;
  - close on a long signal (flip), or after 3 flat signal days in a row.
- At today's VRP the band signal is flat, so expect them to close after 3 flat days unless a short signal comes first.
- Hedge orders go out only when the gap reaches 10 shares, so the book can carry up to 9 shares of delta between hedges.
- `paper.toml` is also the research baseline. The registered `baseline` runs (1 contract, 1-share hedge) no longer match it, so the next experiment needs a fresh `baseline` trial. The "VRP band (paper.toml)" shadow book now has the same rules as the "Hedge band 10" shadow book.
- New entries fill 75% of equity in initial margin, so their size changes with SPY, the strike and the account.
