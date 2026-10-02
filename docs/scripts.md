# Scripts

Run everything from the repo root with the venv active:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

## 1. Offline tests
No IB Gateway needed. Expect `39 passed`.
```bash
PYTHONPATH=src python -m pytest tests -q
```

## 2. Data pipeline
Saves today's snapshot to `data/live/<date>/`.
```bash
PYTHONPATH=src python -m lsgamma.pipeline.build --no-chain    # yfinance only, no Gateway
PYTHONPATH=src python -m lsgamma.pipeline.build --gateway     # full run with the IBKR chain (~3.5 min)
```
- Add `--all-expiries` to include non-Friday expiries.
- `Error 200 (No security definition)` and `Error 10091` are expected and harmless.

## 3. Dry run (no orders)
Prints the forecast, IV, VRP (IV − forecast), signal, and any trade it would make.
```bash
PYTHONPATH=src python -m lsgamma.trading.runner --dry-run --skip-pipeline   # latest saved data, no Gateway
PYTHONPATH=src python -m lsgamma.trading.runner --dry-run                   # fresh data, Gateway open
```

## 4. Smoke test (places paper orders)
Opens 1 ATM call and 1 ATM put, hedges, then closes both and unwinds the shares.

Before running:
- In IB Gateway, untick Configure → Settings → API → Settings → **Read-Only API**.
- Close any other positions in the paper account.
- Run during market hours, after a pipeline run or dry run that day.

```bash
PYTHONPATH=src python -m lsgamma.trading.smoke --yes
```
Check that every line says `Filled` and the account ends flat.

## 5. Daily run (paper trading)
Run at about 10:15 ET with IB Gateway open. It runs the pipeline, forecasts, gets the signal, applies exits, enters if needed, delta hedges, and logs.
```bash
PYTHONPATH=src python -m lsgamma.trading.runner
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
| `signals.parquet` | The daily signal log |
| `trades.parquet` | Opens and closes, with the exit reason and P&L |
| `hedges.parquet` | Hedge fills |

To read a log:
```bash
PYTHONPATH=src python -c "from lsgamma.trading import ledger; print(ledger.read_log('trades'))"
```

## 7. Research experiments
See `research/README.md` for the workflow. To run an experiment (every run is logged to `results/research/<name>/`, gitignored):
```bash
PYTHONPATH=src python research/RV_Forecasting/2026-10-05-har-vs-garch/experiment.py
```
To start a new one:
```bash
cp -r research/_template research/<Topic>/YYYY-MM-DD-short-slug
cp configs/experiments/TEMPLATE.toml configs/experiments/YYYY-MM-DD-short-slug.toml
```

## 8. Changing the rules
All numbers live in `configs/paper.toml`: the VRP bands, forecaster (`garch` or `har`), DTE window, size, exits, slippage, fill timeout and hedge band. No code changes are needed.
