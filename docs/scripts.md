# Scripts

Run everything from the repo root with the venv active:
```bash
source venv/bin/activate
pip install -e ".[dev]"
```
- `pip install -e` installs `lsgamma` from `src/` in editable mode: edits apply at once, and no `PYTHONPATH=src` is needed. Run it once per venv, and again when `pyproject.toml` changes. Older notes that still say `PYTHONPATH=src` work either way.
- Install editable only. A regular `pip install .` breaks the paths to `configs/`, `data/` and `results/`.
- Dependencies are pinned in `pyproject.toml` (`requirements.txt` is gone).

## 1. Offline tests
No IB Gateway needed. Every test should pass.
```bash
python -m pytest -q
```

## 2. Data pipeline
Saves a snapshot to `data/live/<date>/<HHMM>/` (US Eastern run time).
```bash
python -m lsgamma.pipeline.build --no-chain    # yfinance only, no Gateway
python -m lsgamma.pipeline.build --gateway     # full run with the IBKR chain (~3.5 min)
```
- Add `--all-expiries` to include non-Friday expiries.
- `Error 200 (No security definition)` and `Error 10091` are expected and harmless.

## 3. Dry run (no orders)
Prints the forecast, IV, VRP (IV − forecast), signal, and any trade it would make.
```bash
python -m lsgamma.trading.runner --dry-run --skip-pipeline   # latest saved data, no Gateway
python -m lsgamma.trading.runner --dry-run                   # fresh data, Gateway open
```

## 4. Smoke test (places paper orders)
Opens 1 ATM call and 1 ATM put, hedges, then closes both and unwinds the shares.

Before running:
- In IB Gateway, untick Configure → Settings → API → Settings → **Read-Only API**.
- Close any other positions in the paper account.
- Run during market hours, after a pipeline run or dry run that day.

```bash
python -m lsgamma.trading.smoke --yes
```
Check that every line says `Filled` and the account ends flat.

## 5. Daily run (paper trading)
Run at about 10:15 ET with IB Gateway open. It runs the pipeline, forecasts, gets the signal, applies exits, enters if needed, delta hedges, and logs.
```bash
python -m lsgamma.trading.runner
```
| Option | What it does |
|---|---|
| `--skip-pipeline` | Use the latest saved snapshot |
| `--config path.toml` | Use another config (default `configs/paper.toml`) |

## 6. Results
Saved in `results/paper/` (gitignored):

| File | Contents |
|---|---|
| `position.json` | The open position |
| `signals.parquet` | The signal log, one row per run (`date` and `ts`) |
| `trades.parquet` | Opens and closes, with the exit reason and P&L |
| `hedges.parquet` | Hedge fills |

To read a log:
```bash
python -c "from lsgamma.trading import ledger; print(ledger.read_log('trades'))"
```

## 7. Research experiments
See `research/README.md` for the workflow. To run an experiment (every run is logged to `results/research/<name>/`, gitignored):
```bash
python research/RV_Forecasting/2026-10-05-har-vs-garch/experiment.py
```
To start a new one:
```bash
cp -r research/_template research/<Topic>/YYYY-MM-DD-short-slug
cp configs/experiments/TEMPLATE.toml configs/experiments/YYYY-MM-DD-short-slug.toml
```

## 8. Backtesting
Replays R2 option trades into snapshots like the live ones (`data/backtest/v1/`, gitignored), then runs the paper rules over them. Build the data once:
```bash
python -m lsgamma.history.r2 sync                  # copy raw R2 + daily files to data/r2/
python -m lsgamma.history.spread                   # refit configs/backtest_spread.toml from live quotes
python -m lsgamma.history.build [--start --end]    # write the snapshots
python -m lsgamma.history.validate                 # sanity checks on spot, high-low prints and IV
```
- Garman-Klass RV (`rv_gk`, the HAR-GK/HAR-X/RF input) treats a day whose high-low range is over 20× the median of the previous 22 days as a bad print and uses that day's squared close-to-close return instead. `validate` lists every day it caught.
Then run a backtest (no `--exp` = `paper.toml` + `backtest.toml`):
```bash
python -m lsgamma.backtest.run --exp <name> [--start --end]
python -m lsgamma.backtest.run --exp <name> --holdout   # final run only
```
- Every run repeats at 2x spreads (options and hedges) and prints P&L, Sharpe, max drawdown, 5% ES, trades, win rate (net of fees) and holding days.
- It also prints the data gaps: skipped, unfilled, unhedged and unmarked times, and the share of fills priced from the decide-view smile. Read these before the P&L.
- Costs: $0.65 per contract, $0.005 per share, $1 minimum per order (`[backtest]` in `configs/backtest.toml`).
- Outputs go to `results/research/<name>/<timestamp>/` (signals, trades, hedges, equity, events), and each run adds a row to `results/research/registry.parquet`.
- Dates from 2025-01-01 need `--holdout`. Nothing before 2014-06-02 or after 2026-07-10 (R2's last day) runs. The output shows the last trading day actually used.
- Experiments can't change the hold-out, the data window or `[history]` (except `version`); the run stops if they try.
- Several variants in one experiment: put a `[variants.<label>]` table per variant in the TOML and call `run.variants(name, cfg, cfg["variants"])` from `experiment.py`. Each variant runs at 1x and 2x on the development window and is logged as `<name>/<label>`.
- Charts and tables for reports: `lsgamma.backtest.report` (`runs(name)`, `table(sets)` with 2014-2019 / 2020-2024 halves, `standard(sets, folder)` for cumulative P&L, drawdown, yearly, exit reasons and fees, `trials(name)`).
- `[backtest] stop_reset = true` (research only, not in live) blocks a same-side re-entry after a stop until the signal has left that side.
- `[backtest] max_positions = N` (research only, default 1; live holds one position and ignores it) ladders up to N same-side positions, one per signal run. Each exits on its own; flip/flat closes all; hedges are netted into one order per run.

## 9. Changing the rules
All numbers live in `configs/paper.toml`: the VRP bands, forecaster (`garch` or `har`), DTE window, size, exits, slippage, fill timeout and hedge band. After a stop, `stop_cooloff_days` blocks a same-side re-entry (1 = rest of that day; 0 = off). No code changes are needed.

## 10. Research hub
A static site (GSDesign style) that shows the team, then every hypothesis card, its lifecycle, summary, charts, trials and report, a roadmap Gantt and the report library. GitHub Pages rebuilds it on every push to `main` (`.github/workflows/hub.yml`), from committed files only. The site is public, like the repo.
```bash
python -m lsgamma.hub.export              # results/research/registry.parquet -> research/registry.csv
python -m lsgamma.hub.build [--out _site] # build locally, then open _site/index.html
```
- Run `export` when committing an experiment's results, and commit `research/registry.csv` with them. It holds per-trial aggregates only (P&L, Sharpe, drawdown, ES, trades, win rate), never trade rows. It's a separate step because writing into the repo during a run would mark the following runs `-dirty`.
- Plan work in `research/roadmap.toml` (one `[[item]]` per experiment, paper or general research piece). An item without dates goes under Ideas. Once its card exists, set `card = "<slug>"` and the real card replaces it.
- **Live desk:** every real paper run (`lsgamma.trading.runner`, not `--dry-run`) ends by writing `research/desk.json`: the signal history, the open position with P&L marked from that run's chain snapshot, stop and take levels, and the trade log. Commit and push it to refresh the site. `python -m lsgamma.hub.desk` rewrites it by hand from the latest snapshot. Raw quotes are not written, only P&L. It is excluded from the `-dirty` check in `experiments.commit()`, and tests redirect it to a temporary folder.
- **Shadow books** (`configs/shadow.toml`, `python -m lsgamma.trading.shadow`): each listed idea's exact config runs through the backtest engine (`engine.live`) on the daily live snapshots in `data/live`, from 2026-09-26, with its own $250k. Each day uses the folder the live run used (latest at or before that day's logged signal time; otherwise the first usable one). Fills are the snapshot's quoted bid or ask, net of modelled commissions. No orders go to IBKR and nothing is written to the registry. Every real paper run rewrites `research/shadow.json` after `desk.json` (a failure only prints a warning); commit it with `desk.json`. The hub's "View live and shadow strategies" button (Live desk heading, `#strategies`) shows every book against the paper account and its 1x backtest averages. A book with `placeholder` is listed but not run (the hourly signal book waits on hourly snapshots). Intraday schedules are refused.
- **This week** shows counts for the last 7 days: experiments finished (passed/failed), trials logged, reports, paper trades and the change in book P&L.
- **Book P&L:** each desk write also records one row per day (realized + open P&L) in `results/paper/book.parquet`; days before any position count realized only.
- The team section reads `research/team.toml` (name, role, GitHub handle, `photo` in `research/team/`, work-log folders).
- Card status, owner and dates come from the card table and `summary.md`. Charts are the committed `figures/*.png`, and the report is `<slug>.pdf` in the card folder.
- Needs `markdown-it-py` (`pip install -e ".[hub]"`, also in `dev`). `_site/` is gitignored.
- One-time setup: repo Settings → Pages → Source: "GitHub Actions".
- **Cloudflare (lsgamma.quantt.ca):** a Worker serves `_site/` as static assets (`wrangler.toml`). Its `[build]` command builds the site before every `npx wrangler deploy` and preview `npx wrangler versions upload`, so the Cloudflare dashboard only needs the deploy command. The build uses `PYTHONPATH=src` because Cloudflare also runs `pip install .`, and that installed copy would look for `research/` in the wrong place.
