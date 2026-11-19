# 0006. Trade the long/short VRP band again
*Date: 2026-11-19 · Status: Accepted (replaces the 20-delta put pointer of 0004)*

**Context:** Since 2026-11-16 the paper account has traded the stress-sized 20-delta put book (0004), sized to about US$175k with a margin cap (0005). The PM decided to go back to the long/short VRP-band signal that traded before the switch.

**Decision:**
- Remove `book = ...` from `[strategy]` in `configs/paper.toml`. The live runner trades the rules in `paper.toml` again: GARCH forecast; short above +2 vol points, long below −5, otherwise flat; ATM call or put; 1 contract; hedged every share.
- Keep `capital = 175000` and `max_margin = 0.8` (live only). They don't change the 1-contract VRP band, but the margin check still guards each entry.
- The put20 book keeps running as a shadow book.

**Consequences:**
- The 5 short Dec 18 710 puts opened on 2026-11-16 stay open under the VRP-band exit rules:
  - close at 7 DTE (Dec 11);
  - stop at 1x the total credit;
  - profit take at 50%;
  - close on a long signal (flip), or after 3 flat signal days in a row.
- At today's VRP the band signal is flat, so expect them to close after 3 flat days unless a short signal comes first.
- The hedge rebalances every share again (`min_shares = 1`), so expect more hedge orders while the 5 puts are open.
- New entries are 1 contract.
