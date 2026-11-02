# Summary: 2026-11-02-crash-shock

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-crash-shock.pdf](2026-11-02-crash-shock.pdf)

## Result
On the 35% stress-sized `hedged` put book, sizing each entry for a 20% one-day drop with IV at max(60%, 1.5 × the put's IV) (`shock15`) failed the pre-registered bar. It cut the drawdown but lowered the Sharpe ratio. Development window 2014-06-02 to 2024-12-31; reference: the registered 2026-10-22 `hedged` runs.

| Check (`shock15` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Sharpe, full window | 0.51 vs 0.52 | 0.40 vs 0.43 | fail |
| Sharpe, 2014-06 to 2019-12 | 0.84 vs 0.84 | 0.72 vs 0.72 | fail (tie) |
| Sharpe, 2020-01 to 2024-12 | 0.39 vs 0.48 | 0.27 vs 0.38 | fail |
| Max drawdown less severe | $60,228 vs $70,362 | $65,032 vs $75,488 | pass |
| Entries with IV > 40% (floor ≥ 3) | 4 | | met |

Net P&L: `shock15` $92,985 / $73,349 (1x / 2x), against $121,482 / $101,172 for `hedged`.

**Sensitivities** (reported only; they cannot pass this card):
- **`budget25`** (25% budget, today's shock): $80,340 / $72,339; Sharpe 0.48 / 0.43; max drawdown $55,102 / $53,701.
- **`budget15`** (15% budget): $49,858 / $41,938; Sharpe 0.51 / 0.43; max drawdown $29,302 / $31,427.

## Trials
6 trials (3 variants × 1x and 2x, one run), plus the baseline's 2. The `hedged` reference was reused, not rerun.

All six rows are tagged `-dirty` (commits 79b09a1 and 3568520, both containing the pre-registration af47198). Other cards in the batch were being pre-registered during the run, and their uncommitted files were in the shared tree. The engine, `backtest.toml` and this card's files were unchanged.

Two chart fixes were rebuilt with `--report-only`, which adds no trials. The pass bar was not changed.

## What surprised you
- **The shock changed only 4 trades, all in March-April 2020.** No entry before 2020 had IV above 40%, so `shock15` equals `hedged` from 2014 to 2019, and the 2014-2019 Sharpe check could only tie.
- **It mostly cut the winner.**
  - The two stopped puts were sold on 26 February and 2 March, at IV of about 42% or less. The shock left the first unchanged and trimmed the second from 41 to 39 contracts. The two stops still cost $48k.
  - The 13 March put, at about 68% IV, was cut from 100 to 51 contracts, and its profit fell from $70.7k to $36.1k.
  - The 24 March put, a time-exit loser, went from 71 to 51 contracts and lost $4.2k instead of $9.4k.
  - A shock that scales with IV binds after the crash has started, not on its first leg.
- **Smaller fixed budgets don't raise the Sharpe ratio.**
  - 25% and 15% scale every entry to about 70% and 40% of the size.
  - Sharpe is 0.48 and 0.51 at 1x (0.52 for `hedged`), and P&L per dollar of drawdown is similar or lower (1.46-1.70 against 1.73 at 1x).
  - Drawdown scales with the budget. So the budget is a choice of risk appetite, not of edge.

## Caveats
- **In-sample:** the idea comes from the 2026-10-22 results on this window, and the book was chosen after them. Before pre-registration, Claude saw that the reference had 4 entries with IV above 40%, but not their dates or P&L.
- **One episode:** every difference between `shock15` and `hedged` comes from four entries in 2020.
- **Bar design:** the 2014-2019 Sharpe check couldn't be met, because the shock never binds before 2020. The full-window and 2020-2024 checks fail anyway.
- **Not modelled:** margin is not modelled. Large March 2020 fills use the one-contract spread model, and the spread model is fitted on calm 2026 quotes.

## Next step
Archive the 1.5x IV shock. Choosing between 35%, 25% and 15% budgets is a risk-appetite decision for the PM. Protection for the first leg of a crash (for example a cap based on the drop already taken, or a notional cap) would need its own card.
