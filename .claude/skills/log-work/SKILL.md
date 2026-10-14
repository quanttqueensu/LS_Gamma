---
name: log-work
description: Log a work session for an L/S Gamma analyst. Gathers the evidence (commits, files, experiment runs) since their last entry and adds a short update the analyst writes themselves to work-logs/<handle>/YYYY-MM.md. Use when the user runs /log-work or asks to log their work.
---

# Log work

Run at the end of every work session. Claude gathers the evidence. The analyst writes the update.
Repo: `https://github.com/quanttqueensu/LS_Gamma`. Run all commands from the repo root.

## 1. Who
- Handle: `git config lsgamma.handle` (local repo setting, not committed). Email: `git config user.email`.
- No handle (first time): ask for their GitHub handle and save it with `git config lsgamma.handle <handle>`.
  In the table in `work-logs/README.md`, fill in their Name and Topic if blank (ask), or add a row
  `| Name | [<handle>](<handle>/) | Topic |`. Create `work-logs/<handle>/`.

## 2. Since when
- Open their newest monthly file `work-logs/<handle>/YYYY-MM.md`. The top entry ends with `Evidence through: <sha> · <YYYY-MM-DD>`.
- If `git merge-base --is-ancestor <sha> HEAD` succeeds, the range is `<sha>..HEAD`. Otherwise (rebased) use `--since=<date>`.
- No entry yet: use `--since="7 days ago"`.

## 3. Gather the evidence
Exclude `work-logs/` everywhere (`-- . ':(exclude)work-logs'`).
- **Commits:** `git log <range> --author="<email>" --format='%h %ad %s' --date=short -- . ':(exclude)work-logs'`.
  Link each one: `[<sha>](https://github.com/quanttqueensu/LS_Gamma/commit/<sha>) <subject>`.
- **Files:** `git log <range> --author="<email>" --name-only --format= -- . ':(exclude)work-logs' | sort -u`.
  Drop deleted files. Group them, and use relative links from the log file (`../../<path>`):
  - Cards: `research/*/*/README.md`
  - Summaries: `research/*/*/summary.md`
  - Experiments: `research/*/*/experiment.py`, `configs/experiments/*.toml`
  - Reports: `*.pdf`, `*.tex`
  - Code: `src/`. Tests: `tests/`. Other: everything else.
- **In progress:** `git status --porcelain`, excluding `work-logs/`. These are uncommitted, so list the paths without links.
- **Experiment runs:** folders in `results/research/*/` newer than the last entry. Give the name and run count.
  Mark them "(local, not in repo)".
- Leave out empty groups. If there is nothing at all, write "No commits or files this session".

## 4. Ask for the update
Show the evidence, then ask exactly one question:
> In 2–4 sentences, in your own words: what did you work on, what did you learn, and what's next or blocking you?

- Paste the answer **verbatim**. Don't fix spelling, reword, shorten, or add to it.
- If they ask Claude to write it, say no: the update must be theirs, and the evidence is already done.
- If they give one line, accept it.

## 5. Write the entry
- Add the entry to the top of `work-logs/<handle>/YYYY-MM.md` (this month), under the file title.
- If the file is new, its first line is `# <Name> · <Month YYYY>`.
- `<sha>` is `git rev-parse --short HEAD`, taken before any log commit.

```markdown
## YYYY-MM-DD HH:MM · <topic>
**Update (by <first name>):** <their words, verbatim>

**Evidence**
- Commits: [a1b2c3d](https://github.com/quanttqueensu/LS_Gamma/commit/a1b2c3d) Add HAR card · ...
- Cards: [2026-10-15-har-rv](../../research/RV_Forecasting/2026-10-15-har-rv/README.md)
- Code: [HAR.py](../../src/lsgamma/forecasting/HAR.py)
- In progress: research/RV_Forecasting/2026-10-15-har-rv/experiment.py
- Experiment runs: 2026-10-15-har-rv × 3 (local, not in repo)

<sub>Evidence through: a1b2c3d · YYYY-MM-DD</sub>

---
```

## 6. Commit
- Show the entry, then ask: "Commit this log?" If yes, stage only the log file and `work-logs/README.md` if you changed it,
  then `git commit -m "Work log: <handle> YYYY-MM-DD"`.
- No Claude co-author or attribution lines. Never push: tell them to `git push` (or `git pull --rebase` first if it's rejected).
- Never commit data, `results/`, or `.env`.
