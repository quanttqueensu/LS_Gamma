# Summary: 2026-11-02-vvix-cap

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-vvix-cap.pdf](2026-11-02-vvix-cap.pdf)

## Result
The test: on the 35% stress-sized `hedged` put book, cut each entry's stress budget on calm-VVIX days and never size up. The multiplier ran from 0.5x at VVIX's one-year low to 1x from the median up. It failed: at 1x, the Sharpe ratio was lower over the full window and in 2014-2019, and the drawdown was deeper. It passed every check at 2x, by small margins. Development window 2014-06-02 to 2024-12-31.

| Check (`vvix_cap` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Sharpe, full window | 0.48 vs 0.52 | 0.44 vs 0.43 | fail at 1x |
| Sharpe, 2014-06 to 2019-12 | 0.66 vs 0.84 | 0.73 vs 0.72 | fail at 1x |
| Sharpe, 2020-01 to 2024-12 | 0.49 vs 0.48 | 0.41 vs 0.38 | pass |
| Max drawdown less severe | $74,926 vs $70,362 | $74,317 vs $75,488 | fail at 1x |
| Round trips (floor ≥ 30) | 182 | | met |

Net P&L: $109,430 at 1x and $100,144 at 2x, against $121,482 and $101,172 for `hedged`.

Sensitivity `vvix_cap_light` (0.75x to 1x):
- net P&L $113,790 / $104,136;
- Sharpe 0.49 / 0.45;
- 1x drawdown $76,935.

It fails the same way.

## Trials
- 4 trials (2 variants × 1x and 2x, one run), plus the baseline's 2. The `hedged` reference and the uncapped `vvix-sizing/vvix` context runs were reused, not rerun.
- The rows are tagged `af47198-dirty` and `3568520-dirty`. Those are later pre-registration commits of parallel cards in the same batch, and the other cards' uncommitted files were in the shared tree. This card's config, script, the engine and `backtest.toml` were unchanged from its pre-registration (6eae543).
- The pass bar was not changed.

## What surprised you
- **The cap never touched the crash.** VVIX was above its one-year median before the 2020 crash, so all six entries from February to April 2020 were sized at 1x, with the same contract counts as `hedged`. The March 2020 drawdown, which sets every book's maximum, was identical.
- **It cut trades that were small but profitable.**
  - 45% of entries were sized below 1x (mean multiplier at entry 0.88).
  - On the 73 matched trips that were cut, P&L fell from $38.2k to $32.8k. That part is mechanical.
  - Low-VVIX entries made $5.7 per contract in `hedged`: less than the middle tercile ($25.7), but still positive. The high tercile was −$0.1.
- **The drawdown got deeper at 1x even though the book was smaller.**
  - Both books' worst drawdown runs from 2 January 2018 to 17 March 2020.
  - The capped book entered it with less profit, lost $2.4k more in 2018 and made $2.2k less in 2019, mostly in January 2019 as the Q4 2018 path unwound.
- **1x and 2x disagree because of path, not the rule.**
  - 11 round trips at 1x differ between the books (Q4 2018 and mid-2022). They cost $7.3k at 1x.
  - At 2x the divergence fell in other months, and the 2x passes are by 0.01-0.03 of Sharpe.

## Caveats
- **In-sample:** the idea came from the 2026-11-02 VVIX sizing results, including its P&L by VVIX tercile, and the book was chosen after its 2014-2024 results.
- **Path dependence moves the result by thousands of dollars.**
- **VVIX and VIX move together**, so a VVIX effect can't be separated from a vol-level effect.
- **Not modelled:** margin.
- **Spread model:** fitted on calm 2026 quotes; fills of up to 100 contracts use the one-contract model.
- **Data gaps:** about 3.3% of scheduled times are skipped.

## Next step
Archive the capped VVIX tilt. With the uncapped card, the evidence is that VVIX doesn't rank this book's trades:
- sizing up was leverage on March 2020;
- sizing down trims small positive trades.

For a smaller book in calm periods, the 15% and 25% budgets in `2026-11-02-crash-shock` are the direct test.
