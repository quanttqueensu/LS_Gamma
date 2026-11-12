# Hypothesis: widening the long-call hedge band in a trend beats re-hedging every share

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-11-11-trend-long-band` (config: `configs/experiments/2026-11-11-trend-long-band.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed (net P&L −$2,177 vs −$2,060 at 1x; lower in both halves at 1x and 2x) · [summary](summary.md) · [report](2026-11-11-trend-long-band.pdf) |
| **Started** | 2026-11-11 |

## Hypothesis
When the book holds a long call and SPY is trending (10-day efficiency ratio of at least 0.4), letting the share hedge drift up to 30 shares before re-hedging gives higher net P&L than re-hedging every share, without a worse tail.

## Why it matters for the desk
Delta-hedging a long call means shorting SPY. On the paper account, a long December call hedged with 51 to 62 short shares lost $432 on the shares while SPY rallied about $8 (9 November), more than the call gained. A long-gamma book earns from re-hedging when SPY chops, but in a steady trend each re-hedge sells into the move and gives up the call's growing delta. A regime detector that spots trends could let the long call keep more of that move.

The baseline points the other way on average. Over its 30 long-call round trips (2014-06-02 to 2024-12-31, 1x), the share hedge made +$2,115 and the calls lost $3,822. So the hedge was not the source of the long side's loss in aggregate. The test is whether hedging less **only in trends** does better than hedging every share.

If it passes, the change is two research flags (`long_hedge_band`, `trend_er`), which the live runner does not read yet.

## Data
- R2 replay snapshots, version `v1` (`config_hash` b040760187f0), built by `lsgamma.history.build`.
- **Development window:** 2014-06-02 to 2024-12-31. Every result on this card comes from it.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used in this experiment.

## Method
- **Regime detector:** the Kaufman efficiency ratio of SPY's daily closes over the last 10 completed trading days: |10-day price change| divided by the sum of the absolute daily changes. It is 1 for a straight line and near 0 for chop. "Trending" means ER ≥ 0.4, in either direction. It uses completed days only (the backtest's `features.parquet` returns up to yesterday's close), as the live forecast does.
- **Rule** (`engine.long_band`, `engine.trending`): at each hedge time (10:15 ET, once a day, as live), if the book holds a long call and the detector says trending, the engine skips any rebalance smaller than `long_hedge_band` shares and logs a `trend_hold` event. Otherwise it uses the normal band (`[hedge] min_shares = 1`). Short puts are never affected.
- **Variants** (`[variants.<label>.backtest]`, nothing else changed from `paper.toml` + `backtest.toml`):
  - `trend30`: `long_hedge_band = 30`, `trend_er = 0.4` (**primary**, the only variant the pass bar uses)
  - `always30`: `long_hedge_band = 30`, `trend_er = 0` (control: the same band on every long-call day, no detector)
  - `trend15`: `long_hedge_band = 15`, `trend_er = 0.4` (sensitivity: half-width band)
- **Comparison:** the `baseline` (current `paper.toml` + `backtest.toml`, `min_shares = 1`). The registered baseline no longer matches the config (`paper.toml` slippage changed to $0.30, a live-only setting), so a fresh `baseline` trial runs first at 1x and 2x. A direct engine run before registration reproduces baseline trial 1 exactly (net P&L −$2,059.51 at 1x).
- **Spreads:** every variant runs at 1x and 2x spreads. Each variant and multiple is one registry trial: 6 trials, plus 2 for the fresh baseline.
- **Costs:** $0.65 per option contract, $0.005 per share, $1 minimum per order (IBKR Pro Fixed); hedge fills 0.5 cents from spot at 1x.
- Run: `PYTHONPATH=src venv/bin/python research/Deep_Hedging/2026-11-11-trend-long-band/experiment.py` (once). `--report-only` rebuilds charts and tables from the registered runs without new trials.

## Metric and pass bar
Primary variant `trend30` only, compared with the baseline at the same spread multiple; every check must hold at BOTH 1x and 2x:
1. Net P&L of trend30 > baseline over the full window;
2. Net P&L of trend30 > baseline in 2014-06..2019-12;
3. Net P&L of trend30 > baseline in 2020-01..2024-12;
4. |ES 5% (daily)| of trend30 ≤ 1.10 × |ES 5%| of baseline (full window).

**Event floor:** trend30 at 1x must hold back at least 30 hedges (`trend_hold` events); otherwise the verdict is INCONCLUSIVE. Why 30: on the baseline's 190 long-call days, the detector flags about 31% (≈ 60 days), so 30 is about half the days on which it could act.

All checks at both multiples = PASSED; otherwise FAILED. `always30` and `trend15` are reported only and cannot change the verdict. The regime claim (does the detector add anything over a plain wider band?) is read from `trend30` against `always30` in the report, as a diagnostic.

- ES 5% is the mean of the worst 5% of daily net P&L (`lsgamma.backtest.metrics.expected_shortfall`).
- Halves split at 2020-01-01 (`lsgamma.backtest.report.table`).

**Hold-out bar** (only if it passes, and only when the PM asks): `trend30` over 2025-01-01 to 2026-07-10, at 1x and 2x, against the hold-out baseline: net P&L higher (full window) and |ES 5%| within 1.10×.

**In-sample note:** the idea came from the live paper book (November 2026) and from the 2026-10-16 short-only result that long calls lose money over this window. The detector's 0.4 threshold and 10-day lookback were chosen from the feature distribution on this window (it flags about a third of days); no P&L by regime was looked at. A pass is in-sample evidence only.

## If it passes
1. Run `trend30` once on the hold-out (`--holdout`), with the hold-out bar.
2. If that holds, add it as a shadow book next to the paper rules.
3. Then port `long_hedge_band` and `trend_er` to the live runner and set them in `configs/paper.toml`, with a decision record in `docs/decisions/`.

## Changes
- 2026-11-11: run once (6 trials, commit a8ac9e0), after a fresh baseline (2 trials; the registered one predated the live-only `paper.toml` slippage change and is reproduced exactly). The pass bar above was not changed. Verdict: failed at 1x and 2x (`trend30` −$2,177 / −$4,239 against −$2,060 / −$4,122); the event floor was met (37 held hedges). See `summary.md` and `2026-11-11-trend-long-band.pdf`.
- 2026-11-11 (after the run): removed a paper-trade strike from "Why it matters" (no strikes in committed files); the pass bar is unchanged. The fresh baseline differed from the old one in two live-only `[execution]` settings (option slippage and `stock_pad`), neither of which the backtest reads.
