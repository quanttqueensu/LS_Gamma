import argparse
import json
from datetime import date

import numpy as np
import pandas as pd

from lsgamma.history import build, marks, r2, spot, trades

CHECK_TIME = "10:15"
CODES_TIME = "12:15"
TARGET_DTE = 30


def built_days(root):
    return sorted(date.fromisoformat(p.name) for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


def read(root, days, name, hhmm):
    out = []
    for d in days:
        path = root / str(d) / hhmm.replace(":", "") / f"{name}.parquet"
        if path.exists():
            out.append(pd.read_parquet(path).assign(day=d))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def spot_check(root, days, crsp):
    ch = read(root, days, "chain", CHECK_TIME)
    s = ch.groupby("day")["und_price"].median()
    c = crsp.assign(day=pd.to_datetime(crsp["dlycaldt"]).dt.date).set_index("day")
    c = c.loc[c.index.isin(s.index)].astype({k: float for k in ["dlyopen", "dlyhigh", "dlylow"]})
    s = s.loc[c.index]
    inside = ((s >= c["dlylow"]) & (s <= c["dlyhigh"])).mean()
    err = (s - c["dlyopen"]).abs()
    bps = err / c["dlyopen"] * 1e4
    print(f"\n{CHECK_TIME} spot vs CRSP ({len(s)} days)")
    print(f"  inside [low, high]: {inside:.1%}")
    print(f"  |spot - open|: median ${err.median():.3f} ({bps.median():.1f} bps), "
          f"95th ${err.quantile(0.95):.3f} ({bps.quantile(0.95):.1f} bps)")


def iv_check(root, days, idx):
    atm = read(root, days, "atm_iv", CHECK_TIME).dropna(subset=["atm_iv"])
    atm = atm.assign(gap=(atm["dte"] - TARGET_DTE).abs()).sort_values("gap")
    iv = atm.drop_duplicates("day").set_index("day")["atm_iv"]
    vix = idx["vix"].set_axis(idx.index.date)
    ratio = (iv / (vix.reindex(iv.index).astype(float) / 100)).dropna()
    by = ratio.groupby([d.year for d in ratio.index]).agg(["count", "median", "min", "max"])
    print(f"\n{TARGET_DTE}-DTE ATM IV / VIX close at {CHECK_TIME}, by year")
    print(by.round(3).to_string())


def code_devs(day, idx, cfg):
    tr = r2.trades(day)
    asof = trades.at(day, CODES_TIME)
    cut = asof - pd.Timedelta(cfg["lag"])
    ok = trades.window(tr, trades.at(day, build.OPEN), cut, cfg)
    r = build.rate(day, idx)
    fw = spot.forwards(ok, r, spot.NO_DIVS, day, cfg)
    if fw is None:
        return None
    start = cut - pd.Timedelta(cfg["lookback"])
    every = {**cfg, "conditions": tr["conditions"].unique().tolist()}
    allt = trades.window(tr, start, cut, every)
    allt = allt[allt["expiry"].map(lambda e: cfg["min_dte"] <= (e - day).days <= cfg["max_dte"])]
    ivs = marks.trade_ivs(allt, spot.forward_at(fw, allt["ts"], allt["expiry"]), r)
    sm = marks.smiles(ivs[ivs["conditions"].isin(cfg["conditions"])], cfg)
    ivs = ivs[ivs["expiry"].isin(set(sm.index)) & (ivs["k"].abs() <= cfg["smile_k"])]
    dev = (ivs["iv"] - marks.smile_iv(sm, ivs["expiry"], ivs["k"].to_numpy())).abs()
    return pd.DataFrame({"conditions": ivs["conditions"], "dev": dev}).dropna()


def code_check(days, idx, cfg):
    devs = [d for d in (code_devs(day, idx, cfg) for day in days) if d is not None]
    df = pd.concat(devs)
    by = df.groupby("conditions")["dev"].agg(["count", "median"])
    by["allowed"] = by.index.isin(cfg["conditions"])
    by["median"] = by["median"] * 100
    print(f"\n|trade IV - smile| by condition code, vol points ({len(devs)} days, {CODES_TIME})")
    print(by.sort_values("count", ascending=False).round(2).to_string())


def skip_check(root, days, cfg):
    m = json.loads((root / "manifest.json").read_text())
    # a no-trade day skips every grid time
    skips = [s for b in m["builds"] for s in b["skipped"]]
    weight = [len(cfg["grid"]) if s["time"] == "all" else 1 for s in skips]
    skipped = pd.Series(weight, index=[pd.Timestamp(s["date"]).year for s in skips])
    built = pd.Series([len([p for p in (root / str(d)).iterdir() if p.is_dir()]) for d in days],
                      index=[d.year for d in days])
    built = built.groupby(level=0).sum()
    sk = skipped.groupby(level=0).sum().reindex(built.index, fill_value=0)
    share = sk / (sk + built)
    print("\nGrid times skipped, by year")
    print(pd.DataFrame({"built": built, "skipped": sk, "share": share.round(4)}).to_string())
    reasons = pd.Series([s["why"] for s in skips]).value_counts()
    if len(reasons):
        print("  reasons: " + ", ".join(f"{k} {v}" for k, v in reasons.items()))


def main(argv=None):
    cfg = build.load()
    p = argparse.ArgumentParser(description="Sanity checks on a built snapshot version.")
    p.add_argument("--version", default=cfg["version"])
    p.add_argument("--sample", type=int, default=20, help="days for the condition-code check")
    a = p.parse_args(argv)
    root = build.DATA / a.version
    days = built_days(root)
    print(f"{a.version}: {len(days)} days, {days[0]} to {days[-1]}")
    raw = r2.daily_raw()
    idx = build.indices(raw, cfg)
    spot_check(root, days, raw["crsp"])
    iv_check(root, days, idx)
    sample = [days[i] for i in np.unique(np.linspace(0, len(days) - 1, a.sample).astype(int))]
    code_check(sample, idx, cfg)
    skip_check(root, days, cfg)


if __name__ == "__main__":
    main()
