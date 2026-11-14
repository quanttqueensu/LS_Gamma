---
name: research-for-analysts
description: Run an L/S Gamma analyst's experiment end to end from their own hypothesis card - check the card is complete, turn it into backtest variants and a pass bar, pre-register, run once, and write the LaTeX report and summary in the analyst's name. Use when an analyst runs /research-for-analysts <card folder or experiment name>, or asks Claude to run their written experiment card.
---

# Research for analysts

The analyst writes the hypothesis card (`README.md`, copied from `research/_template/README.md`). Claude checks the card is
complete, then does everything else: config, `experiment.py`, one run, charts, report, summary and an independent check. The
backtest engine is not rebuilt: an experiment is a set of parameter changes (variants) run through `lsgamma.backtest`.
The analyst owns the work, and nothing Claude writes carries Claude's name.

Input: `$ARGUMENTS`, a card folder (`research/<Topic>/<YYYY-MM-DD-slug>/`) or an experiment name. If it starts with
`holdout` (or asks for an out-of-sample run), refuse: out-of-sample (OOS) confirmation is run by the PM only.

Files here: `analysts.json` (who may run this), `card_check.md` (the card checklist and guiding questions),
`experiment_template.py`, `report_template.md`. Read `research/README.md` and `docs/decisions/0002-backtest-data-and-timing-rules.md` first.

## Hard rules
- **The card is the analyst's own words.** Never write, rewrite, complete or "suggest wording" for the hypothesis, method,
  data or pass bar, even if asked. Explain that the card has to be theirs and ask guiding questions instead.
  Claude may only change the card's Status, add dated factual Changes notes, and add links to the summary and report.
- **No Claude attribution anywhere:** not in the card, summary, report, code comments, commit messages or trailers
  (no Co-Authored-By, no "Generated with"). The owner and author is the analyst.
- **Never touch live trading:** no edits to `src/lsgamma/trading/`, `src/lsgamma/core/`, `src/lsgamma/pipeline/`,
  `src/lsgamma/history/`, `configs/paper.toml`, `configs/shadow.toml` or `configs/backtest_spread.toml`. Never connect to IBKR,
  never run the live runner or smoke test. In `configs/backtest.toml`, only add a new `[backtest]` research flag with its default off.
- **Development window only:** 2014-06-02 to 2024-12-31. Never pass `--holdout`.
- **Every run is a trial.** Run `experiment.py` once; never rerun for a better result. Rebuilds use `--report-only`. Never delete runs.
- **The pass bar is fixed at pre-registration.** A needed change is a dated Changes note with the reason, written by the analyst.
- **A pass at 1x spreads only is not a pass.**
- **Licensed data (R2/WRDS, Queen's):** committed files show aggregates only. No per-trade rows, strikes, option prices or quotes.
  Never commit `data/`, `results/`, `.env` or figure CSVs.
- **No local paths, `scratchpad` or `.claude` references** in anything committed or compiled.
- **Commits** are made on the experiment branch with the analyst's git identity. Never push: the analyst pushes and opens a PR for the PM.
- **Code style:** short functions, comments of 8 words or fewer, no docstrings; match `lsgamma.backtest`.
- Do the writing yourself. The only subagent is the read-only checker in step 7.

## 0. Guards
1. **Identity.** `git config user.email` must be in `analysts.json` (note the analyst's name and log folder). If it is the PM's
   (gabrielsoler108@gmail.com or the Gabe-Soler noreply address), say the PM uses `/run-experiment-with-report` and stop.
   Otherwise stop and say this skill is for desk analysts listed in `analysts.json`.
2. **Clean tree.** `git status --porcelain` may show only the analyst's card folder (untracked or modified) and untracked
   `figures/*.csv`. Otherwise ask them to commit or stash and stop.
3. **Tooling.** `git fetch` and check `origin/main` has `def holdout` in `src/lsgamma/backtest/run.py` and `def baseline` in
   `src/lsgamma/backtest/report.py`. If not, stop and ask the PM.
4. **Data.** `data/backtest/<version>/manifest.json` must exist for the `[history] version` in `configs/backtest.toml`. If not,
   give `PYTHONPATH=src venv/bin/python -m lsgamma.history.r2 sync` and `... -m lsgamma.history.build` (see `docs/scripts.md`
   section 8) and stop. Also check `venv/bin/python` and `~/.local/bin/tectonic` exist.
5. **Card exists.** The card folder must contain `README.md`. If there is none: explain the workflow (`cp -r research/_template
   research/<Topic>/YYYY-MM-DD-short-slug`, then fill in `README.md`), point them to `card_check.md`'s questions, and stop.

## 1. Card gate
Read the card and check every item in `card_check.md`. Read the topic README and the registry
(`results/research/registry.parquet`) to see whether a matching config already ran.

If anything fails, **stop** and reply with:
- a short list of the gaps, by section name, quoting the card text that fails (e.g. "Pass bar: 'Fixed bottom 20% buy' has no metric or number");
- one or two guiding questions per gap, from `card_check.md`;
- the example cards to read: `research/Deep_Hedging/2026-10-16-hedge-band/README.md` (pass bar layout) and
  `research/Agentic_Routing/2026-11-02-lower-delta/README.md` (variants and event floor);
- "Run `/research-for-analysts <folder>` again when the card is updated."

Write nothing, run nothing, commit nothing. Answer their questions about the backtest or the desk rules if they ask, but don't
draft card text.

**Testability.** If the idea can't be expressed in the backtest, explain why and stop. Examples: other tickers, dates after
2026-07-10, live-only behaviour (order routing, fills), or structures the engine doesn't trade (it trades
`selection.trade_for`: a long call or a short put, one position). Say what could be tested instead, as a question.

## 2. Branch and translate (no runs)
1. **Branch.** If the current branch is `Research/<name>`, stay on it. Otherwise `git checkout -b Research/<name> origin/main`,
   carrying the uncommitted card.
2. **Config** `configs/experiments/<name>.toml`: `[experiment]` (name, topic, owner = the analyst's name),
   `[variants.<label>.<section>]` overrides taken from the card's Method, and `[pass]` taken from the card's pass bar:
   ```toml
   [pass]
   primary = "band10"        # variant the bar judges
   against = "baseline"      # or a reference variant label
   min_events = 0            # event floor; 0 = none
   event = "stop"            # close reason counted for the floor
   event_label = "band10"    # run whose events count (default primary)
   [[pass.check]]
   metric = "pnl"            # any report.table column
   period = "all"            # all / 2014-2019 / 2020-2024
   rule = "higher"           # higher / less_severe / abs_within / not_below
   value = 0.0               # abs_within: ratio; not_below: allowed shortfall
   ```
   Rules: `higher` v > ref; `less_severe` |v| < |ref|; `abs_within` |v| <= value x |ref|; `not_below` v >= ref - value.
   Overrides may touch any `configs/paper.toml` section or `[backtest]` costs/flags; never `holdout_start`, `first_day` or `[history]`.
   **If the card's words allow more than one translation, don't choose.** Stop, quote the ambiguous sentence, and ask the
   analyst to make it precise in the card, then re-run the gate.
3. **Engine switch** (only if no existing setting expresses the idea): the smallest research-only flag in
   `src/lsgamma/backtest/engine.py` or `sim.py`, default off in `configs/backtest.toml`, following the `stop_reset` pattern.
   Add tests in `tests/test_backtest.py` (effect when on, unchanged when off), run `PYTHONPATH=src venv/bin/python -m pytest tests -q`,
   and confirm `engine.backtest(config.load(), ...)` still reproduces baseline trial 1 equity (no registry row).
4. **Baseline.** `report.stale(config.load())` true means a fresh baseline is needed (1x and 2x, counted as trials).
5. **Script** `research/<Topic>/<name>/experiment.py`: copy `experiment_template.py`, set `NAME`, and fill `extra()` with 1-3
   charts of the mechanism (`report.save`, `report.round_trips`, `report.daily`, `out["events"]`). The template's
   `--holdout` flag stays but is never used here.
6. **Topic README:** add a row for the experiment, status planned. If the topic folder is new, give it a README in the same
   sections as the others (question, who, background, code, experiments).
7. **Checks:** `venv/bin/python -m py_compile` on the script, and
   `PYTHONPATH=src venv/bin/python -c "from lsgamma.backtest import config; config.load('<name>')"`; merge each variant with
   `config.merge` and print the merged sections to confirm the overrides land.

## 3. Checkpoint: the analyst approves
Show, in 15 lines or fewer: the hypothesis sentence; each variant as TOML; `[pass]` next to the card sentence it came from;
primary and comparison; the event floor; expected trials (variants x 2, plus a fresh baseline if stale); any engine code.
Wait for the analyst's "go". If they change the plan, the change goes in their card first (re-run the gate on the edit).

## 4. Pre-register and run once
1. If engine code was added: commit it with its tests as "Add research-only <flag> to the backtest engine".
2. Commit the card, config, script and topic README row as "Pre-register <name>". Record the sha.
3. Fresh baseline first if stale: `PYTHONPATH=src venv/bin/python -m lsgamma.backtest.run`.
4. `PYTHONPATH=src venv/bin/python research/<Topic>/<name>/experiment.py`, once (about 25-60 s per variant per multiple).
   If it crashes after trials registered, fix only reporting code and use `--report-only`; add a dated Changes note.
5. Record `report.trials('<name>')` and the baseline's count, and any `-dirty` commit tags with the reason.

## 5. Charts, report, summary
1. **Charts.** Look at every PNG in `figures/` with the Read tool; fix unreadable ones in `experiment.py` only.
2. **Draft** `.claude/research/drafts/experiments/<name>.md` from `report_template.md`, with the analyst's name in line 2.
   Check every claim against the run data (counts, matched trades between runs, years, path dependence); say what is
   mechanical and what may be noise. Backtest facts: spot comes from put-call parity on a 30-minute grid, 10:15-15:45 ET;
   exits and hedges run at the `[schedule]` times. 4-6 pages, sentence-case headings.
3. **Build** `venv/bin/python .claude/skills/strategy-research/md_to_pdf.py .claude/research/drafts/experiments/<name>.md --out research/<Topic>/<name>`.
   Render with `sips -s format png <pdf> --out <scratch png>` and look at it; fix orphaned labels with `###` headings.
   Delete `.log`/`.aux` files.
4. **Summary** `research/<Topic>/<name>/summary.md` from `research/_template/summary.md`: Owner = the analyst, verdict,
   pass-bar table, headline numbers, trials, surprises, caveats, next step, link to the PDF. Plain, factual, no Claude label.
5. **Status** in the card and the topic README row: passed / failed / inconclusive, with links to the summary and the PDF.

## 6. Verdict
INCONCLUSIVE if the event floor fails; PASSED if every check holds at 1x and 2x; FAILED otherwise. Exactly as the
pre-registered `[pass]` says, never reinterpreted.

## 7. Independent check
Start one read-only checker subagent (general-purpose). Give it the experiment name, folder and pre-registration sha. It must not
edit, commit or run `experiment.py`. Checks:
1. The card's pass bar and the `[pass]` table match the pre-registration commit; later `experiment.py` changes touch only charts or reporting and are noted.
2. Every number in the summary and `.tex` recomputes from `results/research/registry.parquet` and the run folders (`lsgamma.backtest.report`).
3. Applying `[pass]` at 1x and 2x gives the stated verdict.
4. The trial count matches the registry; no `holdout=True` rows for this experiment; no `end` on or after 2025-01-01.
5. `git diff origin/main --stat -- src/lsgamma/trading src/lsgamma/core src/lsgamma/pipeline src/lsgamma/history configs/paper.toml configs/shadow.toml` is empty.
6. No per-trade rows, strikes or prices; no local paths, `scratchpad` or `.claude`; and `grep -ril claude` finds nothing in the
   experiment folder, its config, or the branch's commit messages.
7. The card's Hypothesis, Method, Data and pass bar text is unchanged since pre-registration (only Status, Changes and links differ).
8. Spot-check 3-5 analysis claims against the data; render page 1 and a chart page and flag layout problems.
It returns must-fix / should-fix / nit with locations. Fix every must-fix and should-fix, then rebuild the PDF.

## 8. Close
1. `PYTHONPATH=src venv/bin/python -m pytest tests -q`, and the live-diff check from step 7 is empty.
2. `PYTHONPATH=src venv/bin/python -m lsgamma.hub.export`, then commit the card, summary, `experiment.py`, `.tex`, `.pdf`,
   `figures/*.png`, the topic README and `research/registry.csv` as "Add results and report for <name>". Leave figure CSVs untracked.
   If `research/roadmap.toml` has an item for this experiment, set its `card` to `<name>`.
3. Tell the analyst:
   - the verdict and the pass-bar table at 1x and 2x, headline numbers, and what drives the result;
   - the trials, branch and commits;
   - to push: `git push -u origin Research/<name>`, then open a PR to `main` for the PM to review;
   - if it passed: the out-of-sample confirmation is the PM's step (ask the PM to run it); if it failed: what the result rules out;
   - to run `/log-work` to record the session.
