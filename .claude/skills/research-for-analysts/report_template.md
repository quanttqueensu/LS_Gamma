# <Title in sentence case: what was tested, on the SPY gamma book>
*Experiment report · YYYY-MM-DD · <Analyst name>, L/S Gamma Desk, QUANTT*

**Question:** <the hypothesis as a question, one or two sentences>

**Method:**
- Pre-registered backtest: the hypothesis card was committed before any run (commit <sha>).
- The live paper rules (`configs/paper.toml`) are replayed on R2 replay snapshots <version> (config_hash <hash>) over the development window 2014-06-02 to 2024-12-31. The out-of-sample window (2025-01-01 to 2026-07-10) was not used.
- Variants: <label = TOML overrides>. Primary: <label>. Comparison: baseline trial 1, or <reference variant>, at the same spread multiple.
- Every variant was run at 1x and 2x spreads. Costs: $0.65 per contract and $0.005 per share, with a $1 minimum per order. Exits and hedges run at <schedule> ET.

## Result vs the pass bar
<one sentence: every check had to hold at 1x and 2x; what ES and P&L mean (USD, one contract)>

| Check | 1x value | 1x bar | 2x value | 2x bar | Result |
|---|---|---|---|---|---|
| <check> | | | | | pass/fail |

**Verdict: <passed / failed / inconclusive>.** <One or two sentences: the plain answer, and whether the book makes money.>

### Full-window numbers (not part of the bar)
| | baseline 1x | <variant> 1x | ... | <primary> 2x |
|---|---|---|---|---|
| Net P&L | | | | |
| Sharpe | | | | |
| Max drawdown | | | | |
| ES 5% (daily) | | | | |
| Round trips | | | | |
| Commissions (options / hedges) | | | | |

## Charts
![Cumulative net P&L, 1x solid and 2x dashed; baseline grey](figures/cum_pnl.png)

<2-3 sentences: what to see.>

![Drawdown at 1x and 2x spreads](figures/drawdown.png)

<2-3 sentences.>

![Net P&L by year](figures/yearly.png)

<2-3 sentences.>

![Net P&L by side and exit reason, 1x](figures/by_reason.png)

<2-3 sentences.>

![Commissions paid](figures/fees.png)

<2-3 sentences.>

![<experiment-specific chart>](figures/<file>.png)

<2-3 sentences.>

## Analysis
<1-3 short paragraphs on what drives the result. Check every claim against the run data: counts, matched trades between runs, which years, and path dependence (one changed exit shifts later trades). Say what is mechanical and what may be noise.>

## Verdict
<Passed, failed or inconclusive, per the pre-registered bar. Then the next step: archive it, ask the PM for the out-of-sample run, or a follow-up hypothesis (which would need its own card).>

## Caveats
- **In-sample:** <if the idea came from earlier results on 2014-2024, say so; only the out-of-sample run can confirm it>.
- **Size:** <contracts per trade; at one contract the $1 minimum per order is large relative to size>.
- **Spread model:** fitted on about two weeks of calm 2026 live quotes; the 2x run is the stress test.
- **Data gaps:** R2 has no month-end weekdays, so about 3.3% of scheduled times are skipped.
- **Few events:** <how many times the mechanism fired>.
- <anything specific to this experiment>

## Trials
<N> trials for this experiment (<variants> x 1x and 2x, one run of `experiment.py`), plus the baseline's <n>. <Any rebuild with `--report-only`, which adds no trials. Any duplicate configs in other experiments. Any registry rows tagged `-dirty`, and why.> The pass bar was not changed.

