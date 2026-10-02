import argparse

import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.forecasting import FORECASTERS
from lsgamma.pipeline import market

NAME = "2026-10-05-har-vs-garch"
TRADING_DAYS = 252


def returns(cfg):
    spy = market.spy_daily(years=cfg["data"]["years"], symbol=cfg["data"]["symbol"])
    r = np.log(spy["close"]).diff().dropna()
    return r[r.index < pd.Timestamp(cfg["data"]["holdout_start"])]


def realized_var(r, i, horizon):
    # mean daily variance over the next horizon days
    return float((r.iloc[i + 1:i + 1 + horizon] ** 2).mean())


def forecast_dates(r, cfg):
    wf, m = cfg["walk_forward"], cfg["model"]
    first = r.index[0] + pd.DateOffset(years=wf["train_years"])
    last = len(r) - 1 - max(m["horizon"], wf["embargo_days"])
    return [i for i in range(0, last + 1, m["step"]) if r.index[i] >= first]


def qlike(true, pred):
    ratio = true / pred
    return ratio - np.log(ratio) - 1


def run(cfg):
    r = returns(cfg)
    h = cfg["model"]["horizon"]
    rows = []
    for i in forecast_dates(r, cfg):
        past = r.iloc[:i + 1]
        row = {"date": r.index[i], "fold": r.index[i].year, "rv_true": realized_var(r, i, h)}
        for name in cfg["model"]["forecasters"]:
            vol = FORECASTERS[name]().fit(past).predict(h)
            row[name] = vol ** 2 / TRADING_DAYS
        rows.append(row)
    return pd.DataFrame(rows).set_index("date")


def score(df, models):
    losses = pd.DataFrame({m: qlike(df["rv_true"], df[m]) for m in models})
    losses["fold"] = df["fold"]
    by_fold = losses.groupby("fold").mean()
    by_fold.index = by_fold.index.astype(str)
    by_fold.loc["all"] = losses[models].mean()
    return by_fold


def main():
    p = argparse.ArgumentParser(description="HAR vs GARCH: out-of-sample QLIKE by fold")
    p.parse_args()
    cfg = experiments.load_config(NAME)
    run_dir = experiments.start_run(NAME, cfg)
    df = run(cfg)
    table = score(df, cfg["model"]["forecasters"])
    experiments.save(run_dir, df, "forecasts")
    experiments.save(run_dir, table, "qlike_by_fold")
    print(table.round(4).to_string())
    print(f"\n{len(df)} forecasts, run saved to {run_dir}")
    print(f"trials of this experiment so far: {len(experiments.trials(NAME))}")


if __name__ == "__main__":
    main()
