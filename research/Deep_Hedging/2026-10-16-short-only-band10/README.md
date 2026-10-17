# Hypothesis: short-only plus a 10-share hedge band beats short-only alone

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-short-only-band10` (config: `configs/experiments/2026-10-16-short-only-band10.toml`) |
| **Topic** | Deep_Hedging |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | passed (development window; hold-out run still to do) |
| **Started** | 2026-10-16 |

## Hypothesis
Combining short-only with the 10-share hedge band beats short-only alone on net P&L at 1x and 2x, in both halves, without a worse tail.

## Why it matters for the desk
Two rules passed on their own on 2014-2024 (in-sample, no hold-out yet). Short-only (`[signal] long_band = -inf`) lost $773.80 at 1x and $2,351.35 at 2x, against $2,059.5 and $4,122.3 for the baseline. The 10-share band (`[hedge] min_shares = 10`) cut baseline hedge orders from 914 to 469 and lost $1,096.9 at 1x. The short-only book still pays $770 in hedge commissions over 770 hedge orders, almost all at the $1 minimum, which is more than its +$318 gross round-trip P&L at 1x. If the two rules add up, the desk can promote both together. If they don't, the band's gain may depend on the long trades and we should promote only one.

## Data
- R2 replay snapshots, version `v1` (`config_hash` b040760187f0), built by `lsgamma.history.build`.
- **Development window:** 2014-06-02 to 2024-12-31. Every result on this card comes from it.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the 2026-10-16 desk discussion of the baseline on this window (and from the short-only and hedge-band results on the same window), so a pass is in-sample evidence only. Promotion needs one hold-out run.

## Method
- **Book:** short-only (`[signal] long_band = -inf`); otherwise the live `configs/paper.toml` rules: a short put near 30 DTE, 1 contract, hedged once a day at 10:15 ET. Spot comes from put-call parity on the 30-minute grid (10:15-15:45 ET).
- **Rule under test:** at each hedge time, if |target - held| < `min_shares`, skip; otherwise trade the full difference. The band also applies after a close (target 0), as live.
- **Variants:**
  - `band10` (**primary**): `[signal] long_band = -inf`; `[hedge] min_shares = 10`.
  - No sensitivity variant.
- **Reference:** the registered runs of `2026-10-16-short-only/short_only` (1x net P&L −$773.80, 2x −$2,351.35). They have the same config as `band10` except `min_shares = 1`, so they are reused, not rerun. Baseline trial 1 (live rules) is shown in the charts for context only.
- **Runs:** `band10` at 1x and 2x spreads, 2 trials. Costs are $0.65 per contract and $0.005 per share, with a $1 minimum per order (IBKR Pro Fixed); hedge fills 0.5 cents from spot at 1x.
- Run: `PYTHONPATH=src venv/bin/python research/Deep_Hedging/2026-10-16-short-only-band10/experiment.py` (once). `--report-only` rebuilds charts and tables from the registered runs without new trials.

## Metric and pass bar
Primary `band10` against reference `short_only` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. The band lets a short's hedge drift further, which could deepen crash losses.

**Event floor:** `band10` must have at least 20% fewer hedge orders than `short_only` at 1x (at most 616 against 770). Otherwise the band barely changed the hedging and the result is INCONCLUSIVE. 20% is well under the 49% cut the band made on the baseline book, so it only flags a band that hardly binds.

**Hold-out bar** (only if it passes, and only when the PM asks): `band10` against the hold-out baseline (live rules) over 2025-01-01 to 2026-07-10, at 1x and 2x. Net P&L must be higher, and |ES 5%| no more than 1.10 x the baseline's.

## If it passes
Run `band10` once on the hold-out, then shadow mode on paper, then a decision record, then the two-line change in `configs/paper.toml` (`[signal] long_band` and `[hedge] min_shares`).

## Changes
- 2026-10-16: run once (2 trials, pre-registration commit c2f7109). The pass bar above was not changed. Verdict: passed at 1x and 2x (hedge orders cut 49%, above the 20% floor). See `summary.md` and `2026-10-16-short-only-band10.pdf`.
