import argparse

import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.forecasting import FORECASTERS
from lsgamma.pipeline import market
from lsgamma.pipeline.features import term_structure
from lsgamma.signals import SIGNALS
from lsgamma.trading import config

NAME = "2026-10-07-vix-term-gate"
TRADING_DAYS = 252
RULES = ["live", "gated"]


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
    last = len(r) - 1 - max(m["horizon"], wf["embargo_days"])
    rows = []
    for i in range(wf["train_days"] - 1, last + 1, wf["step"]):
        past = r.iloc[i + 1 - wf["train_days"]:i + 1]
        rows.append({"date": r.index[i],
                     "rv": FORECASTERS[m["forecaster"]]().fit(past).predict(m["horizon"]),
                     "realized": realized_vol(r, i, m["horizon"])})
    return pd.DataFrame(rows).set_index("date")


def add_signals(df, mkt, ratio, cfg, live_cfg):
    out = df.join(mkt).assign(iv=lambda x: ratio * x["vix"])
    decide = SIGNALS[live_cfg["signal"]["model"]]
    out["sig_live"] = [decide(rv, iv, live_cfg) for rv, iv in zip(out["rv"], out["iv"])]
    stress = out["vix_vix3m"] >= cfg["gate"]["max_vix_vix3m"]
    out["sig_gated"] = out["sig_live"].mask((out["sig_live"] == "short") & stress, "flat")
    return out


def short_stats(days):
    lost = days[days["realized"] > days["iv"]]
    return {"short_n": len(days),
            "short_prec": (days["iv"] > days["realized"]).mean(),
            "median_loss": (lost["realized"] - lost["iv"]).median()}


def metrics(df):
    rows = {rule: short_stats(df[df[f"sig_{rule}"] == "short"]) for rule in RULES}
    removed = df[(df["sig_live"] == "short") & (df["sig_gated"] == "flat")]
    rows["removed"] = short_stats(removed)
    return pd.DataFrame(rows).T


def by_year(df):
    return pd.concat({y: metrics(g) for y, g in df.groupby(df.index.year)})


def verdict(t, p):
    live, gated = t.loc["live"], t.loc["gated"]
    checks = {
        "precision": gated["short_prec"] >= live["short_prec"] + p["short_gain"],
        "keep": gated["short_n"] >= p["min_keep"] * live["short_n"],
        "days": gated["short_n"] >= p["min_days"],
    }
    return checks, all(checks.values())


def main():
    p = argparse.ArgumentParser(description="VIX term-structure gate on short signals")
    p.parse_args()
    cfg = experiments.load_config(NAME)
    live_cfg = config.load()
    run_dir = experiments.start_run(NAME, cfg)
    r, mkt = load(cfg)
    df = forecasts(r, cfg)

    s = cfg["signal"]
    main_df = add_signals(df, mkt, s["iv_vix_ratio"], cfg, live_cfg)
    table = metrics(main_df)
    years = by_year(main_df)
    sens = metrics(add_signals(df, mkt, s["sensitivity_ratio"], cfg, live_cfg))
    for name, out in [("signals", main_df), ("metrics", table),
                      ("metrics_by_year", years), ("metrics_sensitivity", sens)]:
        experiments.save(run_dir, out, name)

    stress = (main_df["vix_vix3m"] >= cfg["gate"]["max_vix_vix3m"]).mean()
    print(f"{len(df)} forecasts, {df.index[0].date()} to {df.index[-1].date()}, "
          f"inverted on {stress:.1%} of days")
    print(f"\nIV = {s['iv_vix_ratio']} x VIX\n{table.round(3).to_string()}")
    print(f"\nby year\n{years.round(3).to_string()}")
    print(f"\nsensitivity, IV = {s['sensitivity_ratio']} x VIX\n{sens.round(3).to_string()}")
    checks, ok = verdict(table, cfg["pass"])
    print(f"\npass checks: {checks}  ->  {'PASSED' if ok else 'FAILED'}")
    print(f"run saved to {run_dir} (trial {len(experiments.trials(NAME))})")


if __name__ == "__main__":
    main()
