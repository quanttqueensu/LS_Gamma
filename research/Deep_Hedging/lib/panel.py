"""Shared R2 panel for deep-hedging experiments: one 10:15 row set per trading day.

daily: date, spot (decision view), fspot (fill view), market inputs, and the
       strike the book would sell at each delta target (entry_<d>, e.g. entry_20).
puts:  every Friday-expiry put with 1-45 DTE: decision mid/iv/delta/gamma/vega,
       fill-view bid/ask/mid (f_*).
Days before the hold-out only. Built once, shared by every experiment.
"""
import math
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import deep_hedge, engine
from lsgamma.trading import runner, selection
from lsgamma.trading.sizing import put_strike

HHMM = "10:15"
TARGETS = (0.15, 0.20, 0.25)
KEEP = ["expiry", "strike", "dte", "mid", "iv", "delta", "gamma", "vega"]
FOLDER = experiments.ROOT / "deep_hedging_panel" / "v2"
ENTRY = {"entry": {"target_dte": 30, "min_dte": 21, "max_dte": 45}}


def col(target):
    return f"entry_{round(target * 100)}"


def one_day(args):
    d, root = args
    folder = engine.store.folder(engine.at(d, HHMM), root)
    chain, fill = engine.read(folder, "chain"), engine.read(folder, "fill")
    if chain is None:
        return None
    try:
        runner.check(chain)
    except runner.BadSnapshot:
        return None
    puts = chain[(chain["right"] == "P") & chain["dte"].between(1, 45)
                 & chain["expiry"].map(lambda e: e.weekday() == selection.FRIDAY)][KEEP]
    if fill is not None:
        f = fill[fill["right"] == "P"][["expiry", "strike", "bid", "ask", "mid"]]
        puts = puts.merge(f.rename(columns={"bid": "f_bid", "ask": "f_ask", "mid": "f_mid"}),
                          on=["expiry", "strike"], how="left")
    else:
        puts = puts.assign(f_bid=math.nan, f_ask=math.nan, f_mid=math.nan)
    row = {"date": d, "spot": runner.spot(chain),
           "fspot": math.nan if fill is None else float(fill["und_price"].median()),
           "entry_expiry": None, **{col(t): math.nan for t in TARGETS}}
    try:
        t = selection.trade_for("short", chain, ENTRY)
        row["entry_expiry"] = str(t["expiry"])
        for x in TARGETS:
            row[col(x)] = put_strike(t, chain, x)
    except (ValueError, KeyError):
        pass
    return row, puts.assign(date=d)


def build(cfg, start, end, workers=14):
    root = engine.snapshots(cfg)
    feats = pd.read_parquet(root / "features.parquet")
    days = engine.trading_days(feats, start, end)
    with ProcessPoolExecutor(workers) as ex:
        out = [r for r in ex.map(one_day, [(d, root) for d in days], chunksize=20) if r]
    daily = pd.DataFrame([r for r, _ in out])
    mkt = pd.DataFrame([deep_hedge.market(runner.completed(feats, engine.at(d, HHMM)))
                        for d in daily["date"]])
    puts = pd.concat([p for _, p in out], ignore_index=True)
    puts["expiry"] = puts["expiry"].astype(str)
    daily = pd.concat([daily, mkt], axis=1)
    FOLDER.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(FOLDER / "daily.parquet")
    puts.to_parquet(FOLDER / "puts.parquet")
    return daily, puts


def load():
    return pd.read_parquet(FOLDER / "daily.parquet"), pd.read_parquet(FOLDER / "puts.parquet")
