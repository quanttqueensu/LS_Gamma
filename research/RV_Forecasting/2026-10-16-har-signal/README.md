# Hypothesis: on the short-only book, signalling with HAR instead of GARCH raises net P&L without a worse tail

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-har-signal` (config: `configs/experiments/2026-10-16-har-signal.toml`) |
| **Topic** | RV_Forecasting |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed |
| **Started** | 2026-10-16 |

## Hypothesis
On the short-only book (`long_band = -inf`), signalling with the HAR forecaster (`forecaster = "har"`) instead of GARCH makes more net P&L after costs on the R2 option backtest (2014-06-02 to 2024-12-31), at both 1x and 2x spreads and in both halves of the window, without a worse daily tail.

## Why it matters for the desk
The forecaster is the only model input to the VRP signal (`vrp = iv - rv_forecast`), so it decides which days the desk sells gamma. The earlier test, [2026-10-05-har-vs-garch](../2026-10-05-har-vs-garch/README.md), compared HAR and GARCH on forecast error (QLIKE) and HAR failed. But forecast error is not option P&L: a forecaster that is worse on QLIKE can still pick better short days, because the band only cares about the sign of `iv - rv_forecast - 0.02`, not the size of the miss. HAR reacts differently from GARCH after shocks (it stayed high for longer after 2020 in that test), which changes when the short signal turns on. This tests the forecaster on what the desk actually earns. If it passes, the change is one line (`[signal] forecaster`), and `HAR` already ships in `lsgamma.forecasting.FORECASTERS`.

## Data
- R2 replay snapshots `v1` (`config_hash` b040760187f0), option trades from the club R2 bucket replayed with the live code.
- **Development window:** 2014-06-02 to 2024-12-31 (the `[backtest]` default).
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used in this experiment.
- **In-sample note:** the idea comes from the 2026-10-16 desk discussion of the baseline on this same window, so a pass here is in-sample evidence only. Promotion needs one hold-out run.

## Method
- **Book:** short-only (`[signal] long_band = -inf`); otherwise the live `configs/paper.toml` rules. That means a short put near 30 DTE, 1 contract, signal and hedge at 10:15 ET, short band +0.02 (live value, unchanged).
- **Forecast:** `runner.forecast` with `FORECASTERS["har"]`, the same code the live runner uses. It is fit on the last `[backtest] fit_years = 5` years of daily SPY returns from the replay features, completed days only (up to the day before the decision), and forecasts annualised vol over the chosen expiry's DTE in trading days (`round(dte × 252 / 365)`). HAR here is the desk's HAR on squared daily returns, the same model that failed the QLIKE test. Checked before registration on three dates (2016-03-15, 2020-03-20, 2023-06-14): about 1,258 fit days each, ending the previous trading day; no trial was registered.
- **Variants:**
  - `har` (primary): `[signal] forecaster = "har"`, `long_band = -inf`.
  - No sensitivity variant (keeps trials low).
- **Reference:** the registered runs of `2026-10-16-short-only/short_only` (GARCH, `long_band = -inf`; net P&L −$773.80 at 1x, −$2,351.35 at 2x). Their config is the same as `har` except for the forecaster. They are reused, not rerun. Baseline trial 1 (live rules) is shown in the charts for context only.
- **Runs:** `har` at 1x and 2x spreads (2 trials). Costs are $0.65 per contract and $0.005 per share, with a $1 minimum per order; option and hedge fills at the modelled half-spread times the multiple. Spot comes from put-call parity on the 30-minute grid.
- Run: `PYTHONPATH=src python research/RV_Forecasting/2026-10-16-har-signal/experiment.py` (`--report-only` rebuilds charts and tables from the registered runs without new trials).
- **Charts:** the standard set (cumulative P&L, drawdown, yearly, by exit reason, fees), plus three for the mechanism: the RV forecast of GARCH vs HAR over time (monthly mean, with ATM IV), short-signal days per year per forecaster, and the distribution of daily VRP per forecaster against the short band.

## Metric and pass bar
Primary `har` against reference `short_only` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. A forecaster that runs lower would sell more often, including into stress, so the tail guard matters.

**Event floor:** `har` must have at least 30 round trips at 1x (the reference has 100). Fewer than that and HAR has mostly switched the book off, so the result is INCONCLUSIVE rather than a forecaster comparison.

**Hold-out bar** (only if it passes, and only when the PM asks): `har` against the hold-out baseline (live rules) over 2025-01-01 to 2026-07-10, at 1x and 2x. Net P&L must be higher, and |ES 5%| no more than 1.10 x the baseline's.

## If it passes
Run the hold-out once, then run HAR in shadow mode next to GARCH for a few weeks, then a decision record and the one-line change `[signal] forecaster = "har"` in `configs/paper.toml`.

## Changes
- 2026-10-16: run once (2 trials, commit 671df4e; reference reused, not rerun). The pass bar above was not changed. Verdict: failed (full window and the 2020-2024 half, at 1x and 2x). See `summary.md` and `2026-10-16-har-signal.pdf`.
- 2026-10-16 (after the run): chart-only edit to `experiment.py` (the forecast chart's y-axis is capped at 70 and the March 2020 HAR peak is labelled). Figures rebuilt with `--report-only`; no new trials.
