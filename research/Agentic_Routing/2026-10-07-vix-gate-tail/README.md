# Hypothesis: the VIX term gate cuts the worst short-gamma outcomes without giving up the edge

> Fill this card in **before** running anything. Don't change the pass bar after you've seen results.
> If you must change it, add a dated note under "Changes" saying what and why.

| | |
|---|---|
| **Experiment** | `2026-10-07-vix-gate-tail` (config: `configs/experiments/2026-10-07-vix-gate-tail.toml`) |
| **Topic** | Agentic_Routing |
| **Owner** | Gabe Soler (PM) |
| **Status** | failed |
| **Started** | 2026-10-07 |

## Hypothesis
On data no desk experiment has used (Aug 2006 to Sep 2015), skipping short signals when VIX/VIX3M ≥ 1 cuts the expected shortfall of short outcomes by at least 30%, keeps at least 75% of short days, and does not lower the average edge per traded day.

## Why it matters for the desk
`2026-10-07-vix-term-gate` failed its precision bar. Looking at the results afterwards, the gate removed the three worst live shorts in 2015–2025, including 2020-02-28 (−57.5 vol pts), while average edge was unchanged. That finding came from the same data, rests on 3 events, and was not pre-registered, so it proves nothing yet. This card tests it properly on a period nobody has looked at, using a tail metric decided in advance.

If it passes, the gate is a cheap protection against the losses that hurt a short-gamma book most, and it becomes the first rule in the router.

## Data
- SPY daily closes, ^VIX and ^VIX3M closes from yfinance, last 30 years. GARCH needs 5 years of returns before the first forecast, which is available from 2001.
- **Test period (pass bar): 2006-08-01 to 2015-09-30.** It starts when VIX3M data begins and ends just before the period the two earlier experiments used. It includes 2008, the 2010 flash crash, the 2011 US downgrade and August 2015.
- **Reference period:** 2015-10-01 to the hold-out. Reported only. The idea for this card came from it, so it can't count.
- IV is approximated as `0.83 × VIX`. The pass bar uses 0.83; 1.0 × VIX is reported as a sensitivity check only.
- **Hold-out:** from 2025-10-01 onward. Not used.

## Method
- Same as live: every trading day, fit `FORECASTERS["garch"]` on the past 1,255 daily returns, forecast 21 trading days ahead, and get the signal from `SIGNALS["vrp_band"]` with the live bands in `configs/paper.toml`.
- **Gate:** a short signal becomes flat when VIX/VIX3M ≥ 1.0 that day (`pipeline.features.term_structure`). The threshold is fixed and not tuned.
- **Outcome of a short day:** `IV − realized vol` over the next 21 trading days, where realized vol is `sqrt(252 × mean r²)`.
- **Comparison on the same days:** over all live short days, the live outcome is `IV − realized`. The gated outcome is the same, except that a skipped day scores 0 (flat earns nothing and loses nothing).
- **Expected shortfall (ES):** the mean of the worst 5% of those outcomes.
- Run: `PYTHONPATH=src python research/Agentic_Routing/2026-10-07-vix-gate-tail/experiment.py`

## Metric and pass bar
On the test period only, pass if all hold:
1. |ES of gated outcomes| ≤ 70% of |ES of live outcomes|, i.e. at least a 30% cut;
2. gated short days ≥ 75% of live short days;
3. mean edge per gated short day ≥ mean edge per live short day;
4. at least 30 gated short days.

## If it passes
Add the gate as a wrapper around `vrp_band` in `src/lsgamma/signals/` (registered in `SIGNALS`, threshold in `configs/paper.toml`), with tests. Run it in shadow mode next to the live rule for 4 weeks. Confirm on real option P&L (short put with stops) before switching `model` in `configs/paper.toml`.

## Changes
- 2026-10-07: run once (trial 1). The pass bar above was not changed.
