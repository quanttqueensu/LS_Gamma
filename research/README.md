# Research

How the desk tests ideas. Work is organized **by topic**. Each topic's README lists who is working on it and indexes its experiments.

| Folder | What's in it |
|---|---|
| `RV_Forecasting/`, `Deep_Hedging/`, `Agentic_Routing/`, `Risk_Management/` | Topic sandboxes: one folder per hypothesis |
| `_template/` | Copy this to start a new experiment |
| `strategy_research/` | Literature reports (LaTeX + PDF) |
| `Misc_Research_Notes/` | Deep research reports and notes (LaTeX + PDF) |

## The workflow
1. **Pick a topic** and add yourself to its README's "Who's working on it" table.
2. **Copy the template:** `cp -r research/_template research/<Topic>/YYYY-MM-DD-short-slug` and `cp configs/experiments/TEMPLATE.toml configs/experiments/YYYY-MM-DD-short-slug.toml`.
3. **Write the hypothesis card first** (`README.md`): one falsifiable sentence, the data, the hold-out, the metric, and the **pass bar**, all before running anything.
4. **Add a row** to the topic README's experiment table (status: planned).
5. **Run it:** `PYTHONPATH=src python research/<Topic>/<experiment>/experiment.py`. Every run is logged automatically.
6. **Write `summary.md` yourself.** Summaries are written by the analyst who ran the experiment, in their own words. **No AI-written summaries.**
7. **Update the status** in the topic README: passed, failed, inconclusive or promoted.

A finished example: `RV_Forecasting/2026-10-05-har-vs-garch/`.

## Backtesting
To test a rule change on real option trades (R2, 2014-06-02 to 2026-07-10) with the live code:
1. Copy `configs/experiments/TEMPLATE.toml` and set your overrides: any `paper.toml` section (bands, forecaster, DTE window, exits, schedule) plus `[backtest]` costs and dates. The hold-out, data window and `[history]` are fixed.
2. Run `PYTHONPATH=src python -m lsgamma.backtest.run --exp <name>`. It prints P&L, Sharpe, drawdown and 5% ES at 1x and 2x spreads.
3. **Every run is a trial.** Each one adds a row to `results/research/registry.parquet`, so report how many you ran.
4. **The hold-out is 2025-01-01 to 2026-07-10.** It needs `--holdout` and is run once, at the end. Development runs make no entries in the last `[entry] max_dte` (45) days before it.
5. **A result that only passes at 1x spreads does not pass.**
6. **Variants and reports:** list variants as `[variants.<label>]` in the TOML and run them with `lsgamma.backtest.run.variants`. Charts and the two-halves table come from `lsgamma.backtest.report`. Example: `Risk_Management/2026-10-16-stop-levels/`.
7. **PM-run experiments:** the PM can run a whole experiment end to end with Claude (`/run-experiment-with-report`, a PM-only skill kept on the PM's machine, not in this repo). It follows this same process: card committed before the run, development window only, a labelled summary and a report PDF. Analysts keep the manual workflow above.

Commands and data build steps: `docs/scripts.md` section 8. Rules: `docs/decisions/0002-backtest-data-and-timing-rules.md`.

## Work logs
At the end of every session, run `/log-work` in Claude Code. See `work-logs/README.md`.

## Rules
- **Import desk code, don't copy it.** Use `from lsgamma.forecasting import FORECASTERS`, `lsgamma.signals` and so on, so a passing result tests the code that would actually go live.
- **Every parameter goes in the experiment's TOML** (`configs/experiments/<name>.toml`), not hard-coded.
- **Every run is logged.** `experiments.start_run()` writes the config and git commit to `results/research/<name>/<timestamp>/`. Don't delete failed runs: the trial count matters (Lesson 9, Deflated Sharpe).
- **The hold-out is untouchable** until the final run. Change the pass bar only with a dated note on the card.
- **Commit code, cards and summaries only.** Data (`data/`) and run outputs (`results/`) are gitignored. R2 and WRDS data is licensed to Queen's: only aggregate numbers go in summaries, never raw rows. Clear notebook outputs before committing.
- **Notebooks for exploring, scripts for results.** Anything someone else must reproduce runs as `python experiment.py`.

## From experiment to live trading
1. The experiment passes its pre-set bar.
2. The code is rewritten as a clean module in `src/lsgamma/` (`forecasting/`, `signals/` or `core/Algos/Hedging/`) with tests in `tests/`, and registered (`FORECASTERS`, `SIGNALS` or `Hedging/`).
3. It runs in **shadow mode** next to the live rule for a few weeks.
4. The PM approves, and it goes live with one line in `configs/paper.toml`. The decision is recorded in `docs/decisions/`.

## Starting a new topic
Create `research/<New_Topic>/README.md` with the same sections as the others: question for the desk, who's working on it, background reading, code, and experiments.
