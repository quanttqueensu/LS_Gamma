# Summary: 2026-11-02-vvix-sizing

> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM) · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-vvix-sizing.pdf](2026-11-02-vvix-sizing.pdf)

## Result
Scaling the 35% stress budget of the 2026-10-22 `hedged` put book by VVIX's one-year percentile (0.5x to 1.5x, larger when VVIX is high) failed the pre-registered bar. Primary `vvix` against the registered `hedged`, 2014-06 to 2024-12.

| Check (`vvix` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Net P&L, full window | $145,183 vs $121,482 | $130,641 vs $101,172 | pass |
| Net P&L, 2014-06 to 2019-12 | $46,997 vs $49,132 | $46,658 vs $42,687 | fail at 1x |
| Net P&L, 2020-01 to 2024-12 | $98,186 vs $72,350 | $83,984 vs $58,485 | pass |
| ES 5% within 1.10x | −$3,589 vs −$3,016 (1.19x) | −$3,619 vs −$3,094 (1.17x) | fail |
| Max drawdown ≤ $87,500 | $106,599 | $110,464 | fail |
| Round trips (floor ≥ 30) | 181 | | met |

Sensitivities (reported only):
- **`vvix_light`** (0.75x-1.25x): +$135,425 / +$119,332. Max drawdown $88,905 / $93,203, also over the budget.
- **`vvix_reverse`** (larger when VVIX is low): +$85,021 / +$63,829. Max drawdown $29,772; Sharpe 0.55 at 1x (`hedged` 0.52).

## Trials
- 6 trials (3 variants × 1x and 2x, one run at commit 954824c), plus the baseline's 2. The `hedged` reference was reused, not rerun.
- The registry holds 98 trials after the four 2026-11-02 experiments.
- The two `vvix_reverse` rows are tagged `-dirty`: the other three experiments' new figure folders were in the shared working tree. Code and configs were unchanged.
- One chart fix (legend position), rebuilt with `--report-only`; no new trials.

## What surprised you
- **The tilt is mostly leverage on March 2020.** All five entries from mid-February to April 2020 came at 1.39x-1.5x, because VVIX was near the top of its range.
  - They gave 45% of the $23.7k lead at 1x.
  - They pushed the drawdown from $70.4k to $106.6k, over the same January 2018 to March 2020 stretch.
- **Outside that window the tilt adds little:** $112.8k against $99.9k at 1x, Sharpe 0.83 against 0.81, ES 1.05x. `vvix` trailed `hedged` in four of the ten other years (2016, 2018, 2019, 2022).
- **VVIX did not sort per-contract P&L.** In the reference book, mean net P&L per contract by VVIX tercile at entry was $5.7 (low), $25.7 (middle) and −$0.1 (high). That is not the ordering Park (2015) predicts.

## Caveats
- **In-sample:** the book was chosen after its 2014-2024 results. The idea comes from the literature.
- **One episode:** half the lead comes from five entries in early 2020, so a different path through that month would change the result.
- **VVIX and IV move together:** they were extreme together, and the stress rule already sizes up into high IV, so this test can't separate the two.
- **Not modelled:** margin is not modelled. Fills of up to 150 contracts in March 2020 use the one-contract spread model.

## Next step
Archive; don't run the hold-out. A tilt capped at 1x (size down only on calm VVIX) would avoid the drawdown problem. On this evidence its gain would be small, and it would need its own card.
