# Hypothesis: trading an ATM straddle for long gamma and a 20-delta strangle for short gamma makes the VRP-band book's daily P&L less volatile

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-13-straddle-strangle` (config: `configs/experiments/2026-11-13-straddle-strangle.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-11-13 |

## Hypothesis
On the VRP-band rules, opening an ATM straddle (call + put, same strike) on long signals and a 20-delta strangle (put + call) on short signals, 1 contract per leg, gives a lower standard deviation of daily net P&L than the single ATM leg the rules trade now, over the full window and both halves, at 1x and 2x spreads, without a deeper drawdown, a worse tail, or more than $1,000 less net P&L.

## Why it matters for the desk
The VRP band picks long or short gamma, but the structure is fixed: a long ATM call or a short ATM put. A single leg carries a delta that the share hedge has to manage. A straddle is close to delta-neutral at entry and holds more gamma per dollar of delta. A strangle collects premium away from the money, so it pays only when SPY moves past a strike. If the two-leg structures make the book's P&L steadier, the desk could run the same signal with less day-to-day noise. The two halves of the change can also be judged separately: a better long side, a better short side, or both.

## Data
- R2 replay snapshots, version `v1` (`config_hash` b040760187f0), built by `lsgamma.history.build`.
- **Development window:** 2014-06-02 to 2024-12-31. Every result on this card comes from it.
- **Out of sample (OOS):** 2025-01-01 to 2026-07-10. Not used in this experiment.

## Method
- **Base rules:** the current research baseline, `configs/paper.toml` + `configs/backtest.toml`. That is the VRP band (GARCH forecast, short above +2 vol points, long below −5, flat in between), about 30 DTE Friday expiries, 1 contract, hedged every share once a day at 10:15 ET. The live account now trades a different book (the stress-sized 20-delta put, via `[strategy] book`), which backtests ignore.
- **Research switch** (`engine.legs`, `engine.structure_exit`, flags default off):
  - `long_structure = "straddle"`: on a long signal, buy the ATM call and the put at the same strike.
  - `short_structure = "strangle"` with `strangle_delta`: on a short signal, sell the put and the call whose |delta| is nearest the target.
  - Each leg is 1 contract (`[size] quantity`). The legs are one order for commission ($0.65 per contract, $1 minimum per order). Each leg fills at its own quoted half-spread.
  - **The structure exits as one position.** The `paper.toml` rules are applied to the combined P&L (options plus hedge shares) and the combined premium:
    - short stop at 1x the total credit;
    - profit take at 50% of the total credit;
    - long stop at 50% of the total premium;
    - close at 7 DTE, on a flip, or after 3 flat signal days.

    Both legs always close together.
  - The share hedge targets the sum of the legs' deltas.
- **Variants** (`[variants.<label>.backtest]`, nothing else changed):
  - `both`: `long_structure = "straddle"`, `short_structure = "strangle"`, `strangle_delta = 0.20` (**primary**, the only variant the pass bar uses)
  - `straddle_only`: `long_structure = "straddle"`; short signals keep the ATM put
  - `strangle_only`: `short_structure = "strangle"`, `strangle_delta = 0.20`; long signals keep the ATM call
- **Comparison:** baseline trial 1 at the same spread multiple (net P&L −$2,060 at 1x, −$4,122 at 2x). It reproduces exactly with the new flags off.
- **Spreads:** every variant runs at 1x and 2x spreads. Each variant and multiple is one registry trial, 6 trials in total.
- **Costs:** $0.65 per option contract, $0.005 per share, $1 minimum per order (IBKR Pro Fixed). Hedge fills are 0.5 cents from spot at 1x.
- Run: `PYTHONPATH=src venv/bin/python research/Agentic_Routing/2026-11-13-straddle-strangle/experiment.py` (once). `--report-only` rebuilds the charts and tables from the registered runs without new trials.

## Metric and pass bar
**Metric:** `vol`, the standard deviation of daily net P&L in USD (equity change per trading day, flat days included). It is computed in `experiment.py` from `report.daily`.

Primary variant `both` only, compared with the baseline at the same spread multiple. Every check must hold at BOTH 1x and 2x:
1. `vol` of `both` < `vol` of baseline over the full window;
2. `vol` of `both` < baseline in 2014-06..2019-12;
3. `vol` of `both` < baseline in 2020-01..2024-12;
4. max drawdown of `both` < baseline (full window);
5. |ES 5% (daily)| of `both` ≤ 1.10 × |ES 5%| of baseline (full window);
6. net P&L of `both` ≥ baseline net P&L − $1,000 (full window).

Why $1,000: it is about what a second leg costs over the window at one contract. The baseline makes 131 round trips, and a second leg adds a half-spread on each side plus commission, a few dollars per contract per side at SPY's ATM spreads. So "not much worse" means losing no more than that friction. It was set before any run.

**Event floor:** `both` at 1x must open at least 20 straddles and at least 20 strangles. Otherwise the verdict is INCONCLUSIVE. Why 20: the baseline makes 30 long-call and 101 short-put round trips, and 20 is about two-thirds of the scarcer side, enough to judge each structure.

All checks at both multiples = PASSED; otherwise FAILED. `straddle_only` and `strangle_only` are reported only and cannot change the verdict. They show which half of the change drives the result.

- ES 5% is the mean of the worst 5% of daily net P&L (`lsgamma.backtest.metrics.expected_shortfall`).
- Halves split at 2020-01-01 (`lsgamma.backtest.report.table`).

**OOS bar** (only if it passes, and only when the PM asks): `both` over 2025-01-01 to 2026-07-10, at 1x and 2x, against the OOS baseline: `vol` lower, max drawdown lower, |ES 5%| within 1.10×, and net P&L at least the baseline's minus $1,000 (full window).

**In-sample note:** the 2026-10-16 short-only result (long calls lose money on this window) and the 2026-11-11 trend-long-band result (the call's hedge made money while the calls lost it) are both from this window. The 20-delta choice follows the 2026-11-02 lower-delta card, which also used this window. A pass is in-sample evidence only.

## If it passes
1. Run `both` once out of sample (`--holdout`), with the OOS bar.
2. If that holds, add it as a shadow book next to the current rules.
3. Then the live runner needs multi-leg orders (`broker.submit` already sends a `Bag` combo for multiple legs) and the structure exit, with a decision record in `docs/decisions/`.

## Changes
- (none yet)
