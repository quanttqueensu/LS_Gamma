# Hypothesis: on the short-only book, dropping the flat-signal exit raises net P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-no-flat-exit` (config: `configs/experiments/2026-10-16-no-flat-exit.toml`) |
| **Topic** | Risk_Management |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed |
| **Started** | 2026-10-16 |

## Hypothesis
On the short-only book, removing the flat-signal exit (`flat_days = 999`) raises net P&L over the short-only book with the live 3-day flat exit. It does so at 1x and 2x spreads, over the full window and in each half, without a worse daily tail, because shorts keep more of the late time decay and pay fewer spreads.

## Why it matters for the desk
In the baseline, the strategy makes +$1,179 before costs and loses $3,239 to spreads and commissions. Most shorts close after about 9 days on a 3-day flat signal, earning +$1.7 net per trade. The 13 shorts held to the 7-DTE time exit earned +$36 per trade. If holding shorts to expiry management beats churning them, this is a one-line change to `[exit]` that cuts round trips and keeps the decay we are paid for.

## Data
- R2 replay snapshots v1 (config_hash b040760187f0), development window 2014-06-02 to 2024-12-31.
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the baseline's exit-reason breakdown on this same window, so a pass is in-sample evidence. Promotion needs one hold-out run.

## Method
- **Book:** short-only (`[signal] long_band = -inf`); otherwise the live `configs/paper.toml` rules. That means a short put near 30 DTE, 1 contract, hedged daily at 10:15 ET.
- **Exits that remain:** on the short-only book a long signal never fires, so there is no flip exit. Without the flat exit, a short closes only at the 7-DTE time exit, the stop (1x credit) or the profit-take (50% of credit). The embargo before the hold-out still applies.
- **Variants:**
  - `short_only` (reference): the same config as `2026-10-16-short-only/short_only`. It is rerun here for a like-for-like comparison, at 2 extra trials.
  - `no_flat` (primary): `[exit] flat_days = 999`.
  - `flat10` (sensitivity): `[exit] flat_days = 10`. It is reported only.
- **Runs:** each variant at 1x and 2x spreads. Costs are $0.65 per contract and $0.005 per share, with a $1 minimum per order. That makes 6 trials. Baseline trial 1 (live rules) is shown for context.

## Metric and pass bar
Primary `no_flat` against reference `short_only` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. The tail guard matters because holding shorts longer could deepen crash losses.

**Event floor:** `no_flat` must have at least 20 time exits at 1x. The reference has about 13. Otherwise the mechanism barely changed anything and the result is INCONCLUSIVE.

**Hold-out bar** (only if it passes, and only when the PM asks): `no_flat` against the hold-out baseline (live rules) over 2025-01-01 to 2026-07-10, at 1x and 2x. Net P&L must be higher, and |ES 5%| no more than 1.10 x the baseline's.

## If it passes
Combine it with the other passing rules (short-only, hedge band) into one candidate. Run the hold-out once on that combination, then shadow mode, then a decision record, then the one-line change `[exit] flat_days` in `configs/paper.toml`.

## Changes
- 2026-10-16: run once (6 trials, commit dbf1d11). The pass bar above was not changed. Verdict: failed (2x full window and the 2014-2019 half). See `summary.md` and `2026-10-16-no-flat-exit.pdf`.
- 2026-10-16 (after the run): chart-only edits to `experiment.py` (turnover legend headroom, `tick_labels` for the holding box plot). Figures rebuilt with `--report-only`; no new trials.
