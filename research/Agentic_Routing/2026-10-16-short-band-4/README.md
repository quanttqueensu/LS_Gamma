# Hypothesis: on the short-only book, a +4 vol point short band raises net P&L

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-16-short-band-4` (config: `configs/experiments/2026-10-16-short-band-4.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM); run by Claude at the PM's request |
| **Status** | failed |
| **Started** | 2026-10-16 |

## Hypothesis
On the short-only book, raising the short band from +2 to +4 vol points raises net P&L at 1x and 2x, in both halves, because each trade's edge rises more than the trade count falls.

## Why it matters for the desk
The short-only book (`2026-10-16-short-only/short_only`) makes +$318 gross over 100 round trips at 1x but loses $773.80 net (−$2,351.35 at 2x): about −$5.6 net per round trip at 1x and −$21.2 at 2x. Each trade's edge is too thin to pay its spreads and hedge commissions. If a wider band keeps only the richest VRP readings, each trade should carry more edge, and with fewer trades the desk pays fewer costs. This is the router's first threshold question: at what VRP is a short worth putting on? If it passes, it is a one-line change to `[signal] short_band`.

## Data
- R2 replay snapshots `v1` (`config_hash` b040760187f0), option trades from the club R2 bucket replayed with the live code.
- **Development window:** 2014-06-02 to 2024-12-31 (the `[backtest]` default).
- **Hold-out:** 2025-01-01 to 2026-07-10. Not used.
- **In-sample note:** the idea comes from the 2026-10-16 desk discussion of the baseline on this same window, so a pass here is in-sample evidence only. Promotion needs one hold-out run.

## Method
- **Book:** short-only (`[signal] long_band = -inf`); otherwise the live `configs/paper.toml` rules. That means a short put near 30 DTE, 1 contract, `max_positions = 1`, the 10:15 ET signal and hedge, and the live exits (3 flat days, 7 DTE, stop at 1x credit, profit at 50% of credit). A short opens when VRP (ATM IV minus the GARCH RV forecast) is above `short_band`, and a day below the band counts as flat.
- **Variants:**
  - `band4` (primary): `[signal] long_band = -inf`, `short_band = 0.04`.
  - `band3` (sensitivity, reported only): `[signal] long_band = -inf`, `short_band = 0.03`.
- **Reference:** the registered runs of `2026-10-16-short-only/short_only` at 1x and 2x (short band +2 vol points). Their saved config matches the current `paper.toml` + `backtest.toml` with `long_band = -inf`, so they are not rerun. Baseline trial 1 (live rules) is shown in the charts for context.
- **Path dependence:** a wider band also changes exits. A short closes after 3 straight days with VRP at or below the band, so with a +4 band a fall to +3.5 already counts as flat, and shorts may close sooner. With one position slot the entry dates differ too. This compares whole books, not matched trades.
- **Runs:** each variant at 1x and 2x spreads (4 trials). Costs are $0.65 per contract and $0.005 per share, with a $1 minimum per order; fills at the modelled half-spread times the multiple.
- **Charts** (`figures/`): the standard set (cumulative P&L, drawdown, yearly, by exit reason, fees), plus round trips and net P&L per round trip per book (edge per trade against trade count), the distribution of VRP at entry per book (aggregates only), and short-signal days per year per book.
- Run: `PYTHONPATH=src python research/Agentic_Routing/2026-10-16-short-band-4/experiment.py` (`--report-only` rebuilds charts and tables from the registered runs without new trials).

## Metric and pass bar
Primary `band4` against reference `short_only` at the same spread multiple. Every check must hold at **both 1x and 2x**:
1. Net P&L is higher over the full window;
2. Net P&L is higher in 2014-06 to 2019-12;
3. Net P&L is higher in 2020-01 to 2024-12;
4. |ES 5% (daily)| is no more than 1.10 x the reference's |ES 5%| over the full window. The guard matters because fewer, richer-VRP entries cluster in stressed markets.

**Event floor:** `band4` must have at least 30 round trips at 1x (every close counts). Below that, the per-trade edge is too noisy to judge and the result is INCONCLUSIVE. The reference has 100. On the reference's signal series (an input, the same for every book), VRP is above +4 vol points on 221 days in 74 separate spells, so the floor should be reachable.

**Verdict:** INCONCLUSIVE if the floor fails; PASSED if all four checks hold at 1x and 2x; FAILED otherwise.

**Hold-out bar** (only if it passes, and only when the PM asks): `band4` against the hold-out baseline (live rules) over 2025-01-01 to 2026-07-10, at 1x and 2x. Net P&L must be higher, and |ES 5%| no more than 1.10 x the baseline's.

**Trials:** 4 (2 variants x 2 multiples). The reference is reused from `2026-10-16-short-only` (2 trials, not rerun).

## If it passes
Combine it with the other passing short-only rules into one candidate. Run the hold-out once on that combination, then shadow mode, then a decision record, then the one-line change `[signal] short_band` in `configs/paper.toml`.

## Changes
- 2026-10-16: run once (4 trials, commit 6b9adb9; the `short_only` reference reused, not rerun). The pass bar above was not changed. Verdict: failed (1x full window, and 2020-2024 at both spreads). See `summary.md` and `2026-10-16-short-band-4.pdf`.
