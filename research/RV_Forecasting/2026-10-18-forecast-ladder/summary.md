# Summary: 2026-10-18-forecast-ladder

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-18 · **Verdict:** failed (all three candidates)

Full report: [2026-10-18-forecast-ladder.pdf](2026-10-18-forecast-ladder.pdf)

## Result
No candidate beat the live GARCH(1,1) forecast of 22-day SPY realized variance on the pre-registered bar. Each had to have lower QLIKE **and** a smaller median calm-day bias (VIX below 20) in each of 2000-2013, 2014-2019 and 2020-2024. Forecasts covered 6,267 days from 2000; no target window reached the 2025 hold-out.

| Period | Check | GARCH | har_gk | harx | rf |
|---|---|---|---|---|---|
| 2000-2013 | QLIKE | 0.264 | 0.795 fail | 0.379 fail | 0.365 fail |
| 2000-2013 | calm-day bias (vol pts) | +2.28 | +5.83 fail | +2.68 fail | +1.52 pass |
| 2014-2019 | QLIKE | 0.369 | 0.364 pass | 0.348 pass | 0.407 fail |
| 2014-2019 | calm-day bias | +3.12 | +3.50 fail | +2.55 pass | +1.77 pass |
| 2020-2024 | QLIKE | 0.538 | 0.684 fail | 0.802 fail | 0.753 fail |
| 2020-2024 | calm-day bias | +3.17 | +5.79 fail | +4.34 fail | +3.94 fail |

Over 2000-2024 all three have significantly higher QLIKE than GARCH (Newey-West t +2.4, +3.0, +2.1). The random forest has the lowest median bias overall (+1.8 vs +2.4 vol points). Card 2 (P&L) is not run; GARCH stays live.

## Trials
One run at commit b5f5413, three candidates: 3 trials. The post-hoc checks in the report read the saved forecasts (and one refit on one date); they add no trials. The pass bar was not changed.

## What surprised you
- **GARCH wins in the spikes.** From 20 February to 15 April 2020 realized vol had a median of 56.1%; GARCH forecast 46.3%, the candidates 22-29%. GARCH updates daily with each squared return; the candidates refit monthly. The random forest can't forecast above its training targets (its highest forecast in that stretch was 26.2%). The worst 5% of days are 47-59% of every model's QLIKE.
- **After 2020 the regressions run high in calm years** (2021, 2023, 2024), with the crash inside their 5-year window, as the live HAR did in `2026-10-16-har-signal`.
- **Calm-day bias is partly skew.** On calm days in 2020-2024 GARCH's median vol bias was +3.2 points, but its mean forecast variance was only 0.85 of mean realized variance. A forecast of expected variance should sit above the typical calm month. Lowering the median bias means under-forecasting the spikes, which QLIKE punishes.
- **A bad data point.** The features file has one Garman-Klass value of 899% vol, on 2006-01-26 (SPY moved 0.55%). From the April 2006 to the January 2011 refit it sets the `har_gk` coefficients near zero. On 2008-10-10 its forecast was 13.6% with the point and 64.2% without it. That explains `har_gk`'s 2008 collapse. With the point fixed and the candidates refit (checked after the run), every candidate still fails 2000-2013 (QLIKE 0.303, 0.519 and 0.362 against 0.264). The verdict doesn't depend on it: every candidate fails 2020-2024 on both checks, and those windows don't contain the point. The live signal and the option backtest use GARCH on returns and are not affected.

## Caveats
- Forecast accuracy is not P&L.
- Overlapping 22-day targets (the Newey-West t allows for this).
- 2020 and 2022 have few calm days (35 and 23).
- The monthly refit, the 5-year window and the random-forest settings were fixed in advance; other choices would be new trials.
- Garman-Klass RV is zero in the replay features from 2026, so any hold-out would need a fallback.

## Next step
Archive. Follow-ups, each needing its own card:
- fix the 2006-01-26 Garman-Klass print in the backtest's daily data with a validation rule (a PM decision, since the history build is shared);
- a daily-refit log-HAR, if the desk wants another forecasting rung;
- or change the signal rather than the forecast: compare IV with a median-type forecast so the signal goes short more often in calm stretches. That is close to always-short (`2026-10-17-always-short`), so state its expected value over that book first.
