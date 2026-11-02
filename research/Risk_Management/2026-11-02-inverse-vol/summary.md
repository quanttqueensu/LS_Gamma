# Summary: 2026-11-02-inverse-vol

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-11-02 · **Verdict:** failed

Full report: [2026-11-02-inverse-vol.pdf](2026-11-02-inverse-vol.pdf)

## Result
The test scaled the 35% stress budget of the 2026-10-22 `hedged` put book by VIX's one-year percentile, from 1.5x at its one-year low to 0.5x at its high (prior close). It failed: Sharpe was lower in 2014-2019 at both spreads. The primary is `vix_inv`; the reference is the registered `2026-10-22-stress-sized-puts/hedged`; the window is 2014-06-02 to 2024-12-31.

| Check (`vix_inv` vs `hedged`) | 1x | 2x | |
|---|---|---|---|
| Sharpe, full window | 0.62 vs 0.52 | 0.48 vs 0.43 | pass |
| Sharpe, 2014-06 to 2019-12 | 0.78 vs 0.84 | 0.61 vs 0.72 | fail |
| Sharpe, 2020-01 to 2024-12 | 0.57 vs 0.48 | 0.42 vs 0.38 | pass |
| Max drawdown less severe | $41,489 vs $70,362 | $45,307 vs $75,488 | pass |
| Round trips (floor ≥ 30) | 183 | | met |

The book still makes money, but less: $95,448 at 1x and $74,804 at 2x, against $121,482 and $101,172.

Sensitivities (reported only):
- **`vix_inv_cap`** (capped at 1x, never above the budget): $83,364 / $67,415; Sharpe 0.59 / 0.47; max drawdown $38,887 / $42,464. Sharpe in 2014-19 was 0.77 at 1x.
- **`rv_inv`** (monthly realized vol, a stand-in for 1/GARCH): $101,878 / $93,306; Sharpe 0.65 / 0.59; max drawdown $51,083 / $48,190. Sharpe in 2014-19 was 0.67 / 0.71.

## Trials
- 6 trials (3 variants × 1x and 2x, one run), plus the baseline's 2. The `hedged` reference was reused, not rerun.
- All six rows are tagged `-dirty`, under commits 3ab834b, af47198, 79b09a1 and 3568520.
  - Other cards of the same batch committed pre-registrations and wrote files in the shared working tree during the run.
  - Each tagged commit contains this card's pre-registration (e31b598) and changes no engine code, `backtest.toml` or this card's files.
- The pass bar was not changed.

## What surprised you
- **The Sharpe gain is the March 2020 cut, nothing more.**
  - All five entries from 26 February to 17 April 2020 came at 0.50-0.61x, so the 100- and 71-contract entries became 49 and 37.
  - From 19 February to 30 April 2020 the book made $9.0k against $21.7k, and its drawdown fell from $70k to $41k.
  - Outside that window Sharpe was lower: 0.75 against 0.81 at 1x.
- **Before 2020 the tilt sized the wrong way around shocks.**
  - It was larger just before spikes (the mid-August 2015 entry, at 1.14x, was stopped) and smaller just after.
  - The entry the day after 24 August 2015, at 0.5x, made about half the reference's.
  - In 2014-2019, mean daily P&L fell 11% but its volatility only 4%.
- **Per-contract P&L was higher at low VIX ($21.9 against $7.9 at high VIX),** but the high-VIX tercile carried $71.2k of the reference's $113.2k round-trip net. That came from a few large crash entries, and the tilt halves those.

## Caveats
- **In-sample:** the book was chosen after its results. Earlier cards on it (slope sizing, `vvix_reverse`) had shown that sizing down in stress raises the full-window Sharpe.
- **One episode:** the full-window Sharpe and drawdown results rest on five early-2020 entries.
- **Rank, not ratio:** this is VIX's one-year percentile, not literal 1/VIX. It reverses quickly after a spike.
- **Model limits:** the spread model was fitted on calm 2026 quotes; margin is not modelled; about 3.3% of scheduled times are skipped.

## Next step
Archive and don't run the hold-out. The tilt acts like a smaller crash budget and trails the fixed budget outside March 2020. `2026-11-02-crash-shock` (15%/25% budgets and the 1.5×IV stress) is the direct test of cutting crash size.
