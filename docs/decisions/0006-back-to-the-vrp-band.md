# 0006. Trade the long/short VRP band again, 5 contracts with a 10-share hedge band
*Date: 2026-11-19 · Status: Accepted (replaces the 20-delta put pointer of 0004)*

**Context:** Since 2026-11-16 the paper account has traded the stress-sized 20-delta put book (0004), sized to about US$175k with a margin cap (0005). The PM decided to go back to the long/short VRP-band signal that traded before the switch.

**Decision:**
- Remove `book = ...` from `[strategy]` in `configs/paper.toml`. The live runner trades the rules in `paper.toml` again: GARCH forecast; short above +2 vol points, long below −5, otherwise flat; ATM call or put.
- **Hedge band:** `[hedge] min_shares` goes from 1 to 10. The book re-hedges only when its delta gap reaches 10 shares, as in `2026-10-16-hedge-band`, which passed in-sample at 1x and 2x (−$1,097 vs −$2,060 at 1x; 469 hedge orders vs 914). That evidence is in-sample only: the out-of-sample run has not been done.
- **Size:** `[size] quantity` goes from 1 to 5 contracts per position. The margin check (0005) still sizes each entry down to 80% of equity. Estimated from Reg T, an ATM short put plus its share hedge takes about US$35k of initial margin per contract. Short entries will probably be cut to about 4 contracts, while long calls (premium paid plus their short-share hedge) fit 5.
- Keep `capital = 175000` and `max_margin = 0.8` (live only).
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
- New entries are up to 5 contracts, as the margin check allows.
