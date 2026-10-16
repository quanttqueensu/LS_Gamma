# Hypothesis: net P&L has an interior peak in the number of laddered positions

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-max-positions` (config: `configs/experiments/2026-10-16-max-positions.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed |
| **Started** | 2026-10-16 |

## Hypothesis
With the live rules, net P&L as a function of the maximum number of open same-side positions (1, 2, 3, 4, 6 or 8, laddered one per signal run) peaks at an interior value: it rises from 1 and falls before 8, at both 1x and 2x spreads.

## Why it matters for the desk
The book holds one SPY position at a time. Between entry days the signal often stays on, and the desk does not act on it. Laddering into a persistent signal uses more of the $250k. If P&L peaks at an interior N, that N is a sizing rule. If P&L only falls with N, or only rises, the rule is "don't ladder" or "use the capital limit". Each answer changes how the desk would scale up.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the hypothesis is the PM's prior, not a pattern seen in earlier results. The window has been used by five earlier experiments, though, so this is still development-window evidence.

## Method
- **Rules:** the live rules in `configs/paper.toml` (long call / short put on the VRP band, 1 contract, daily hedge at 10:15 ET), unchanged.
- **New, research-only:** `[backtest] max_positions` (default 1; live always holds 1 and does not read it).
  - While the signal stays on the same side, the engine opens one more position per signal run until N are open. Each position has its own entry date, expiry, strike and premium, and its own time, stop and profit exits.
  - A flip or flat signal closes every open position. The stop cool-off and embargo apply as before.
  - Hedges are netted: one share order per run, for the sum of the position targets, shared across positions for P&L and fees.
  - With N = 1 the engine reproduces baseline trial 1 exactly (tested).
- **Variants:** `pos2`, `pos3`, `pos4`, `pos6`, `pos8` (`max_positions` = 2, 3, 4, 6, 8). N = 1 is baseline trial 1.
- **Why 8 is the maximum:** a short put plus its hedge needs about $28-31k under Reg-T at SPY ~$600 (naked put about 20% of spot plus premium, plus 50% of ~50 hedge shares; baseline peak estimate $30.9k). So 8 fit in $250k. The report shows the estimated peak Reg-T margin for each N against $250k.
- **Runs:** each variant at 1x and 2x spreads. Costs are $0.65 per contract and $0.005 per share, with a $1 minimum per order. 10 trials.

## Metric and pass bar
Net P&L (daily equity, USD) for N in {1, 2, 3, 4, 6, 8}. It passes only if all of these hold at **both 1x and 2x**:
1. The full-window net P&L is highest at an interior N (2, 3, 4 or 6).
2. That peak beats both ends (N = 1 and N = 8) by at least $500. That is about a quarter of the baseline 1x loss, so a wiggle doesn't count as a peak.
3. In each half (2014-06 to 2019-12 and 2020-01 to 2024-12), the highest-P&L N is also interior.

**Event floor:** at N = 8 (1x) there must be at least 30 ladder entries (entries while another position is open). Otherwise the result is INCONCLUSIVE, because laddering barely happened.

Reported, not part of the bar: Sharpe on $250k, ES 5% and max drawdown against N, plus margin use and average open positions.

**Hold-out bar** (only if it passes, and only when the PM asks): the dev-window peak N, chosen by rule 1 at 1x, beats the hold-out baseline (N = 1) on net P&L at 1x and 2x over 2025-01-01 to 2026-07-10.

## If it passes
Run the hold-out once (`experiment.py --holdout`). If it holds, the live runner would need multi-position support, which is a code change to the live engine. Then shadow mode, then a decision record, then setting the size in `configs/paper.toml`.

## Changes
- 2026-10-16: run once (10 trials, commit e5e0806). The pass bar above was not changed. Verdict: failed (best N = 1 at 1x and 2x, in both halves). See `summary.md` and `2026-10-16-max-positions.pdf`.
