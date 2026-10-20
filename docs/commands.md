# Commands

Quick reference for working in this repo with Claude Code. For the Python scripts (tests, pipeline, experiments), see [scripts.md](scripts.md).

## Desk commands
| Command | When | What it does |
|---|---|---|
| `/log-work` | End of every work session | Collects your commits and files as evidence, asks for a 2–4 sentence update in your own words, and saves it to `work-logs/<you>/`. See [work-logs/README.md](../work-logs/README.md). |

## Claude Code basics
| Command | What it does |
|---|---|
| `/help` | List every command |
| `/clear` | Start a fresh conversation (do this between unrelated tasks) |
| `/compact` | Shrink a long conversation so Claude stays fast |
| `/resume` | Pick up an earlier conversation |
| `! <command>` | Run a shell command yourself, e.g. `! git status` |
| `@path/to/file` | Point Claude at a file |

## First session
```bash
git pull
python3 -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q   # all should pass
```
Then read [research/README.md](../research/README.md), pick a topic, and end the session with `/log-work` and `git push`.

## Rules
- Write your own experiment `summary.md`, with no AI.
- Never commit `data/`, `results/` or `.env`. R2 and WRDS data is licensed to Queen's.
- Trading is paper only.
