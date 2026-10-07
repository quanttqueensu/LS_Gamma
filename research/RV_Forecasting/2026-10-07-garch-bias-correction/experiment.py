import argparse

import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.forecasting import FORECASTERS
from lsgamma.pipeline import market
from lsgamma.signals import SIGNALS
from lsgamma.trading import config

NAME = "2026-10-07-garch-bias-correction"
TRADING_DAYS = 252
MODELS = ["live", "corrected"]


def load(cfg):
    d = cfg["data"]
    spy = market.spy_daily(years=d["years"], symbol=d["symbol"])
    vix = market.indices(years=d["years"])["vix"]
    r = np.log(spy["close"]).diff().dropna()
    r = r[r.index < pd.Timestamp(d["holdout_start"])]
    return r, vix.reindex(r.index).ffill() / 100


def realized_vol(r, i, horizon):
    # vol over the next horizon days
    return float(np.sqrt((r.iloc[i + 1:i + 1 + horizon] ** 2).mean() * TRADING_DAYS))


def forecasts(r, cfg):
    wf, m = cfg["walk_forward"], cfg["model"]
    last = len(r) - 1 - max(m["horizon"], wf["embargo_days"])
    rows = []
    for i in range(wf["train_days"] - 1, last + 1, wf["step"]):
        past = r.iloc[i + 1 - wf["train_days"]:i + 1]
        rows.append({"date": r.index[i],
                     "live": FORECASTERS[m["forecaster"]]().fit(past).predict(m["horizon"]),
                     "realized": realized_vol(r, i, m["horizon"])})
    return pd.DataFrame(rows).set_index("date")


def correct(df, cfg):
    m, step = cfg["model"], cfg["walk_forward"]["step"]
    err = np.log(df["live"] / df["realized"])
    # only errors whose target window has finished
    lag = -(-m["horizon"] // step)
    bias = err.shift(lag).rolling(m["bias_window"] // step).median()
    return df.assign(bias=bias, corrected=df["live"] * np.exp(-bias)).dropna()


def add_signals(df, vix, ratio, live_cfg):
    out = df.assign(iv=ratio * vix.reindex(df.index))
    decide = SIGNALS[live_cfg["signal"]["model"]]
    for m in MODELS:
        out[f"sig_{m}"] = [decide(rv, iv, live_cfg) for rv, iv in zip(out[m], out["iv"])]
    return out


def qlike(true, pred):
    ratio = true ** 2 / pred ** 2
    return ratio - np.log(ratio) - 1


def metrics(df):
    rows = {}
    for m in MODELS:
        short = df[df[f"sig_{m}"] == "short"]
        long = df[df[f"sig_{m}"] == "long"]
        rows[m] = {"bias": (df[m] - df["realized"]).median(),
                   "qlike": qlike(df["realized"], df[m]).mean(),
                   "flat_share": (df[f"sig_{m}"] == "flat").mean(),
                   "short_n": len(short),
                   "short_prec": (short["iv"] > short["realized"]).mean(),
                   "long_n": len(long),
                   "long_prec": (long["realized"] > long["iv"]).mean()}
    return pd.DataFrame(rows).T


def by_year(df):
    return pd.concat({y: metrics(g) for y, g in df.groupby(df.index.year)})


def verdict(t, p):
    live, cor = t.loc["live"], t.loc["corrected"]
    checks = {
        "bias": abs(cor["bias"]) < p["max_abs_bias"],
        "short": cor["short_n"] >= p["min_days"]
                 and cor["short_prec"] >= live["short_prec"] + p["short_gain"],
        "long": cor["long_n"] >= p["min_days"] and cor["long_prec"] > p["min_long_precision"],
    }
    return checks, all(checks.values())


def main():
    p = argparse.ArgumentParser(description="Bias-corrected GARCH vs live GARCH in the VRP band")
    p.parse_args()
    cfg = experiments.load_config(NAME)
    live_cfg = config.load()
    run_dir = experiments.start_run(NAME, cfg)
    r, vix = load(cfg)
    df = correct(forecasts(r, cfg), cfg)

    s = cfg["signal"]
    main_df = add_signals(df, vix, s["iv_vix_ratio"], live_cfg)
    table = metrics(main_df)
    years = by_year(main_df)
    sens = metrics(add_signals(df, vix, s["sensitivity_ratio"], live_cfg))
    for name, out in [("forecasts", main_df), ("metrics", table),
                      ("metrics_by_year", years), ("metrics_sensitivity", sens)]:
        experiments.save(run_dir, out, name)

    print(f"{len(df)} forecasts, {df.index[0].date()} to {df.index[-1].date()}")
    print(f"\nIV = {s['iv_vix_ratio']} x VIX\n{table.round(3).to_string()}")
    print(f"\nby year\n{years.round(3).to_string()}")
    print(f"\nsensitivity, IV = {s['sensitivity_ratio']} x VIX\n{sens.round(3).to_string()}")
    checks, ok = verdict(table, cfg["pass"])
    print(f"\npass checks: {checks}  ->  {'PASSED' if ok else 'FAILED'}")
    print(f"run saved to {run_dir} (trial {len(experiments.trials(NAME))})")


if __name__ == "__main__":
    main()
