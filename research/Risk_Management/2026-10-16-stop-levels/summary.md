# Summary: 2026-10-16-stop-levels

> Written by Claude at the PM's request (an exception to the analyst-written rule). Analysts still write their own summaries.
> Only aggregate numbers here: no raw data, no per-trade rows (R2/WRDS data is licensed).

**Owner:** Gabe Soler (PM); run by Claude at the PM's request · **Date finished:** 2026-10-16 · **Verdict:** failed (H1 failed, H2 failed)

Full report: [2026-10-16-stop-levels.pdf](2026-10-16-stop-levels.pdf)

## Result
Neither hypothesis met its pre-set bar. The comparison is baseline trial 1 on the development window 2014-06-02 to 2024-12-31, and every check had to hold at both 1x and 2x spreads.

**H1 (`tight`: short stop 0.5x credit, long stop 0.25x premium): failed.** The tail got slightly worse instead of 20% better.

| | 1x | 2x | Bar | |
|---|---|---|---|---|
| ES 5% (daily), full window | −98.1 (base −96.5) | −107.1 (base −104.5) | size ≤ 0.80 × base | fail |
| ES 5%, 2014-06..2019-12 | −49.0 (base −47.9) | −55.8 (base −53.2) | less severe than base | fail |
| ES 5%, 2020-01..2024-12 | −134.1 (base −132.9) | −144.4 (base −142.9) | less severe than base | fail |
| Net P&L, full window | −$2,331 (base −$2,060) | −$4,540 (base −$4,122) | ≥ base − $300 | pass 1x, fail 2x |

**H2 (`profit25`: short take-profit at 25% of credit): failed.** It beat the baseline in the first half but lost to it in the second half and over the full window.

| | 1x | 2x | Bar | |
|---|---|---|---|---|
| Net P&L, full window | −$2,153 (base −$2,060) | −$4,171 (base −$4,122) | > base | fail |
| Net P&L, 2014-06..2019-12 | −$922 (base −$986) | −$1,451 (base −$1,511) | > base | pass |
| Net P&L, 2020-01..2024-12 | −$1,231 (base −$1,073) | −$2,720 (base −$2,611) | > base | fail |
| ES 5%, full window | −96.6 | −104.5 | size ≤ 1.10 × base | pass |

`both` (all three changes, reported only) was the worst variant: −$2,556 at 1x and −$4,723 at 2x.

## Trials
6 trials for this experiment (3 variants × 2 spread multiples, from one run of `experiment.py`), plus the baseline's 2, so 8 in total. The charts were rebuilt once with `--report-only` to fix an axis. That reads saved runs and adds no trial. The only change to `experiment.py` after pre-registration is that chart axis (`sharey="row"`). The run and the evaluation are unchanged.

`tight` has exactly the same config as `cool1` in 2026-10-16-stop-cooloff. The two runs gave identical registry metrics, daily P&L and trade P&L at 1x and 2x, so the same test is registered twice across the desk (4 trials). The pass bar was not changed.

## What surprised you
- **The rules barely fire.** In ten and a half years the tight stops fired only 3 times (2015 and 2020) and the 25% profit-take 7 to 9 times, mostly in 2020. The tail days are almost the same days in every run: 127 of the 129 worst-5% days are shared between `tight` and the baseline. The worst day (−$468) is the same in all four runs.
- **A once-a-day stop can't cut a daily tail.** The stop is checked at 10:15, after the move that triggers it. The 3 stopped positions lost $1,297 at 1x. In the baseline the same positions recovered part of the loss and closed on a flip signal for −$924.
- **The profit-take won on its own trades and lost afterwards.** On the positions it closed early, it made $254 more than the baseline (1x). The shorts opened after those exits, in 2020-2021, lost more than that.

## Caveats
- The idea came from the baseline on the same window, so this is in-sample. A pass would still have needed a hold-out run.
- Very few events (3 stops, 7 to 9 profit-takes), almost all in 2015 and 2020-2021 (one profit-take in 2024), so the differences are close to noise.
- Daily checks only, as live (10:15). The replay snapshots support checks every 30 minutes (extra `[schedule] hedge` times, using parity-implied spot), but that wasn't tested here.
- One contract: the $1 order minimum is large relative to size (hedge commissions are about 78% of fees).
- The spread model was fitted on about two weeks of calm 2026 quotes. Month-end R2 days are missing, and 3.3% of scheduled times were skipped.

## Next step
Archive both changes and keep `[exit]` in `configs/paper.toml` as it is. No hold-out run is needed. If the desk wants a real loss limit, the next question is a different mechanism, for example a portfolio-level or intraday check, or sizing. Tighter or looser levels for the same daily per-position stop are not worth testing.
