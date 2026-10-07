import argparse
import math

import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.forecasting import FORECASTERS
from lsgamma.pipeline import market
from lsgamma.pipeline.features import term_structure
from lsgamma.signals import SIGNALS
from lsgamma.trading import config

NAME = "2026-10-07-vix-gate-tail"
TRADING_DAYS = 252


def load(cfg):
    d = cfg["data"]
    spy = market.spy_daily(years=d["years"], symbol=d["symbol"])
    idx = market.indices(years=d["years"]).reindex(spy.index).ffill()
    r = np.log(spy["close"]).diff().dropna()
    r = r[r.index < pd.Timestamp(d["holdout_start"])]
    mkt = pd.DataFrame({"vix": idx["vix"] / 100, "vix_vix3m": term_structure(idx)["vix_vix3m"]})
    return r, mkt.reindex(r.index)


def realized_vol(r, i, horizon):
    # vol over the next horizon days
    return float(np.sqrt((r.iloc[i + 1:i + 1 + horizon] ** 2).mean() * TRADING_DAYS))


def forecasts(r, cfg):
    wf, m = cfg["walk_forward"], cfg["model"]
    start = pd.Timestamp(cfg["data"]["test_start"])
    last = len(r) - 1 - max(m["horizon"], wf["embargo_days"])
    rows = []
    for i in range(wf["train_days"] - 1, last + 1, wf["step"]):
        if r.index[i] < start:
            continue
        past = r.iloc[i + 1 - wf["train_days"]:i + 1]
        rows.append({"date": r.index[i],
                     "rv": FORECASTERS[m["forecaster"]]().fit(past).predict(m["horizon"]),
                     "realized": realized_vol(r, i, m["horizon"])})
    return pd.DataFrame(rows).set_index("date")


def short_days(df, mkt, ratio, cfg, live_cfg):
    out = df.join(mkt).assign(iv=lambda x: ratio * x["vix"])
    decide = SIGNALS[live_cfg["signal"]["model"]]
    out["signal"] = [decide(rv, iv, live_cfg) for rv, iv in zip(out["rv"], out["iv"])]
    out = out[out["signal"] == "short"].copy()
    out["edge"] = out["iv"] - out["realized"]
    out["kept"] = out["vix_vix3m"] < cfg["gate"]["max_vix_vix3m"]
    return out


def es(x, tail):
    # mean of the worst tail share
    n = max(1, math.ceil(tail * len(x)))
    return float(np.sort(x)[:n].mean())


def metrics(s, tail):
    gated = s["edge"].where(s["kept"], 0.0)
    kept = s[s["kept"]]
    rows = {}
    for rule, out, days in [("live", s["edge"], s), ("gated", gated, kept)]:
        rows[rule] = {"short_n": len(days),
                      "mean_edge": days["edge"].mean(),
                      "precision": (days["edge"] > 0).mean(),
                      "es": es(out.to_numpy(), tail),
                      "worst": out.min(),
                      "big_losses": int((out < -0.10).sum()),
                      "total": out.sum()}
    return pd.DataFrame(rows).T


def split(s, cfg):
    end = pd.Timestamp(cfg["data"]["test_end"])
    return {"test": s[s.index <= end], "reference": s[s.index > end]}


def verdict(t, p):
    live, gated = t.loc["live"], t.loc["gated"]
    checks = {
        "es": abs(gated["es"]) <= (1 - p["es_cut"]) * abs(live["es"]),
        "keep": gated["short_n"] >= p["min_keep"] * live["short_n"],
        "edge": gated["mean_edge"] >= live["mean_edge"],
        "days": gated["short_n"] >= p["min_days"],
    }
    return checks, all(checks.values())


def main():
    p = argparse.ArgumentParser(description="VIX term gate: tail risk of short signals")
    p.parse_args()
    cfg = experiments.load_config(NAME)
    live_cfg = config.load()
    run_dir = experiments.start_run(NAME, cfg)
    r, mkt = load(cfg)
    df = forecasts(r, cfg)
    tail, s = cfg["pass"]["tail"], cfg["signal"]

    tables = {}
    for label, ratio in [("main", s["iv_vix_ratio"]), ("sensitivity", s["sensitivity_ratio"])]:
        days = short_days(df, mkt, ratio, cfg, live_cfg)
        if label == "main":
            experiments.save(run_dir, days, "short_days")
        for period, part in split(days, cfg).items():
            tables[(label, period)] = metrics(part, tail)
    out = pd.concat(tables)
    experiments.save(run_dir, out, "metrics")

    print(f"{len(df)} forecasts, {df.index[0].date()} to {df.index[-1].date()}")
    for (label, period), t in tables.items():
        ratio = s["iv_vix_ratio"] if label == "main" else s["sensitivity_ratio"]
        print(f"\n{period} period, IV = {ratio} x VIX\n{t.round(3).to_string()}")
    checks, ok = verdict(tables[("main", "test")], cfg["pass"])
    print(f"\npass checks (test period): {checks}  ->  {'PASSED' if ok else 'FAILED'}")
    print(f"run saved to {run_dir} (trial {len(experiments.trials(NAME))})")


if __name__ == "__main__":
    main()
