# Hypothesis: HAR on Garman-Klass RV, HAR-X and a random forest each forecast 22-day SPY realized vol better than the live GARCH, with less calm-day bias

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-18-forecast-ladder` (config: `configs/experiments/2026-10-18-forecast-ladder.toml`) |
| **Topic** | RV_Forecasting |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | planned |
| **Started** | 2026-10-18 |

## Hypothesis
Each of three forecasters (HAR on Garman-Klass RV, HAR-X adding VIX and last week's return, and a random forest on the HAR-X inputs) has lower out-of-sample QLIKE than the live GARCH(1,1) for SPY's mean daily variance over the next 22 trading days, **and** a smaller median bias on calm days, in each of 2000-2013, 2014-2019 and 2020-2024.

This is card 1 of 2 (forecast accuracy only). Card 2 puts the passers into the option backtest's signal and judges net P&L.

## Why it matters for the desk
The desk's backtests show the signal-timed book loses mainly because it sits out calm stretches: on the signal's flat days the GARCH forecast runs above realized vol (`2026-10-17-always-short`, corrected 2026-10-18; `2026-10-07-garch-bias-correction`). A forecast that tracks calm regimes better would put the signal short more often when shorting pays. The ladder follows the desk report `2026-09-27-ml-rl-for-realised-volatility-forecasting` (Christensen, Siggaard & Veliyev 2022: RV lags, implied vol and the past week's return are the most useful inputs; random forests beat HAR with minimal tuning).

## Data
- `data/backtest/v1/features.parquet` (the backtest's completed-day features: SPY daily from CRSP, Garman-Klass RV from daily OHLC, VIX from CBOE). Every input is also in the live pipeline (yfinance SPY OHLC and ^VIX).
- Forecast dates: 2000-01-03 until the last day whose 22-day target window ends before 2025-01-01. Training data from 1995 (5-year window).
- This extends before the option backtest's development window (2014-06 to 2024-12). Forecast accuracy needs no option data, and 2000-2013 adds 2001-02, 2008 and 2011.
- **Hold-out:** from 2025-01-01 onward. Not used, and no target window reaches it.

## Method
- **Target:** mean squared daily close-to-close log return over the next 22 trading days (the variance GARCH forecasts). Forecast at the close of day t uses completed days up to t only (the live runner's information at 10:15 on day t+1).
- **Reference:** live GARCH(1,1) (`forecasting/GARCH.py`, unchanged), refit every day on the trailing 5 years of returns, as live (`fit_years = 5`), predicting 22 days ahead.
- **Candidates** (new research-only code in `src/lsgamma/forecasting/HARX.py` and `RF.py`, kept out of the live `FORECASTERS` registry):
  - `har_gk`: direct 22-day HAR, target regressed on daily, weekly and monthly Garman-Klass RV.
  - `harx`: `har_gk` plus VIX (as daily variance) and last week's return (5-day sum of log returns).
  - `rf`: random forest on the `harx` inputs. 300 trees, minimum 20 rows per leaf, seed 0. Fixed before the run, not tuned.
- **Walk-forward:** candidates refit on the first trading day of each month on the trailing 5 years, using only rows whose 22-day target is complete before that day. Between refits they forecast daily from the newest completed day.
- Forecasts are floored at 5% annualized vol. Days without VIX are dropped for every model.
- Run once: `PYTHONPATH=src venv/bin/python research/RV_Forecasting/2026-10-18-forecast-ladder/experiment.py`.

## Metric and pass bar
- **QLIKE** = realized/forecast − ln(realized/forecast) − 1 on daily variance, averaged over forecast days (lower is better).
- **Calm-day bias** = median of forecast vol minus realized vol, in vol points, over days when the completed-day VIX is below 20.
- **Each candidate passes if, in every period (2000-2013, 2014-2019, 2020-2024):**
  1. its mean QLIKE is lower than GARCH's; **and**
  2. its absolute median calm-day bias is smaller than GARCH's.
- **Event floor:** at least 250 calm days in each period, else that candidate is INCONCLUSIVE.
- Verdict per candidate: PASSED / FAILED / INCONCLUSIVE. The card passes if at least one candidate passes. Passers go to card 2.
- Reported only, not in the bar: full-window scores, overall median bias, a Newey-West t-statistic of the QLIKE gap (22 lags, overlapping targets), yearly charts, bias by VIX level.
- **Why these numbers:** three periods so a pass can't come from one regime; the last two match the backtest halves. VIX 20 is a common calm/stress split and is above the median VIX of the signal's flat days (14.9). The 5% floor only keeps QLIKE finite if a regression forecast goes negative; the report states how often it binds.
- **Hold-out bar:** the same two checks on 2025-01-01 onward, for card 2's promoted model. Garman-Klass RV is zero in the replay features from 2026-01-02 (parity closes have no high or low), so a hold-out run needs a fallback first. That gets settled in card 2, before any hold-out.
- **In-sample note:** the calm-bias idea comes from the desk's 2014-2024 backtests and diagnostics. The 2000-2013 period has not been used by the desk for forecast tests (the 2026-10-07 VIX-gate test used 2006-2015 with a different question).

## Trials
One run of `experiment.py`, scoring three candidates against the GARCH reference: counted as 3 trials toward the desk's tally. Forecast-only runs are logged under `results/research/2026-10-18-forecast-ladder/` (the backtest `registry.parquet` holds option-backtest runs only).

## If it passes
Card 2: the passing forecaster(s) replace GARCH in the signal on the 25-delta short-only book (reference `2026-10-17-otm-put/put25`), at 1x and 2x, in both halves, with the ES guard. That needs a research-only backtest switch that passes the features table to these forecasters. Only after card 2 and a hold-out run: shadow mode, then a `runner.py` change and `paper.toml` line with a decision record (PM).

## Changes
- 2026-10-18 (before the run): the PM confirmed the calm threshold (VIX < 20) and that every check must hold in each of the three periods.
