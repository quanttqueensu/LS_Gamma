import argparse
import copy
import fcntl
import json
import os
import time

import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import config, engine, metrics, report


def start_run(name, cfg):
    # run folders are named to the second
    while True:
        try:
            return experiments.start_run(name, cfg)
        except FileExistsError:
            time.sleep(0.2)


def register(row):
    path = experiments.ROOT / "registry.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        # parallel runs must not drop rows
        fcntl.flock(lock, fcntl.LOCK_EX)
        df = pd.DataFrame([row])
        if path.exists():
            df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
        tmp = path.with_suffix(".tmp")
        df.to_parquet(tmp)
        os.replace(tmp, path)  # readers never see half a file


def trial(name, cfg, start, end, holdout=False, mult=None, root=None, cache=None):
    cfg = copy.deepcopy(cfg)
    if mult is not None:
        cfg["backtest"]["spread_mult"] = mult
    out = engine.backtest(cfg, start, end, holdout, root, cache)
    run = start_run(name, cfg)
    for k, df in out.items():
        experiments.save(run, df, k)
    m = metrics.summary(out, cfg)
    span = out["span"].iloc[0]
    register({"experiment": name, "run": str(run.relative_to(experiments.ROOT)),
              "commit": experiments.commit(), "version": cfg["history"]["version"],
              **engine.manifest(engine.snapshots(cfg, root)),
              "start": str(start), "end": str(end), "last_day_used": span["last_day"],
              "holdout": holdout, "spread_mult": cfg["backtest"]["spread_mult"],
              "schedule": json.dumps(cfg["schedule"]), **m})
    return {"spread_mult": cfg["backtest"]["spread_mult"], **m, "run": str(run),
            "last_day_used": span["last_day"]}


def mults(cfg):
    bt = cfg["backtest"]
    return sorted({bt["spread_mult"], bt["stress_mult"]})


def variants(name, cfg, table, root=None):
    # development window only; one trial per variant and mult
    base = {k: v for k, v in cfg.items() if k != "variants"}
    start, end = engine.day(base["backtest"]["start"]), engine.day(base["backtest"]["end"])
    caches, out = {}, {}
    for v, over in table.items():
        config.check_pins(over, f"{name}/{v}")
        vcfg = config.merge(base, over)
        key = (vcfg["signal"]["forecaster"], vcfg["backtest"]["fit_years"])
        cache = caches.setdefault(key, {})
        out[v] = [trial(f"{name}/{v}", vcfg, start, end, False, m, root, cache)
                  for m in mults(vcfg)]
    return out


def held(name):
    reg = report.registry()
    return bool(((reg["experiment"] == name) & (reg["holdout"] == True)).any())


def holdout(name, label, cfg, base, root=None):
    # final run only: once per variant
    exp = f"{name}/{label}"
    if held(exp):
        raise SystemExit(f"{exp} already has a hold-out run; refused")
    over = cfg["variants"][label]
    config.check_pins(over, exp)
    vcfg = config.merge({k: v for k, v in cfg.items() if k != "variants"}, over)
    start = engine.day(base["backtest"]["holdout_start"])
    end = engine.day(base["history"]["last_day"])
    out = {label: [trial(exp, vcfg, start, end, True, m, root, {}) for m in mults(vcfg)]}
    if report.stale(base, holdout=True):
        out["baseline"] = [trial("baseline", base, start, end, True, m, root, {})
                           for m in mults(base)]
    return out


def table(rows):
    df = pd.DataFrame(rows).set_index("spread_mult").drop(columns=["run", "last_day_used"])
    df = df.round(3)
    gaps = [c for c in df.columns if c.split("_share")[0] in metrics.GAPS] + ["decide_smile"]
    return (df.drop(columns=gaps).to_string() + "\n\ndata gaps (counts, share of scheduled times)\n"
            + df[gaps].to_string())


def main():
    p = argparse.ArgumentParser(description="Backtest the paper rules on R2 replay snapshots")
    p.add_argument("--exp", default=None, help="configs/experiments/<exp>.toml")
    p.add_argument("--holdout", action="store_true", help="final run only: allow 2025-01-01+")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    a = p.parse_args()
    cfg = config.load(a.exp)
    bt = cfg["backtest"]
    start = a.start or (bt["holdout_start"] if a.holdout else bt["start"])
    end = a.end or (cfg["history"]["last_day"] if a.holdout else bt["end"])
    start, end = engine.day(start), engine.day(end)
    engine.check_window(cfg, start, end, a.holdout)
    cache = {}
    rows = [trial(a.exp or "baseline", cfg, start, end, a.holdout, m, cache=cache)
            for m in mults(cfg)]
    used = rows[0]["last_day_used"]
    print(f"{a.exp or 'baseline'}  {start} to {end}{'  HOLD-OUT' if a.holdout else ''}"
          f"  (last trading day used: {used})")
    print(table(rows))
    for r in rows:
        print(f"  {r['spread_mult']}x: {r['run']}")


if __name__ == "__main__":
    main()
