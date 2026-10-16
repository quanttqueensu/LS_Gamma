# Risk Management

**Question for the desk:** which exit rules (stops, profit-takes, cool-offs after a stop) cut the worst losses of the gamma book without giving up its edge after costs?

## Who's working on it
| Name | GitHub | Role | Since |
|---|---|---|---|
| Gabe Soler (PM) | G-S-design | PM, experiments run by Claude at the PM's request | 2026-10-16 |

## Background reading
- Onboarding: Lessons 8 and 9 (`docs/education/`)
- Decisions: `docs/decisions/0003-stop-cooloff-and-order-minimum.md` (stop cool-off, $1 order minimum)
- Kaminski & Lo (2014), "When do stop-loss rules stop losses?" (a stop is an exit rule plus a re-entry rule)

## Code
Exit rules are in `src/lsgamma/trading/exits.py`, with settings in `[exit]` of `configs/paper.toml`. Backtests run them through `lsgamma.backtest` on R2 replay snapshots. Research-only rules (such as `[backtest] stop_reset`) live in `src/lsgamma/backtest/engine.py` until they are promoted.

## Experiments
| Date | Hypothesis | Owner | Status | Summary |
|---|---|---|---|---|
| 2026-10-16 | [Tighter stops cut the tail; a 25% profit-take adds P&L](2026-10-16-stop-levels/README.md) | Gabe Soler (PM) | planned | |
| 2026-10-16 | [A longer wait after a stop beats the 1-day cool-off](2026-10-16-stop-cooloff/README.md) | Gabe Soler (PM) | planned | |
