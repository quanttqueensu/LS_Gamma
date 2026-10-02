# Research

How the desk tests ideas. Work is organized **by topic**. Each topic's README lists who is working on it and indexes its experiments.

| Folder | What's in it |
|---|---|
| `RV_Forecasting/`, `Deep_Hedging/`, `Agentic_Routing/` | Topic sandboxes: one folder per hypothesis |
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
