"""Training episodes for the deep hedger, from the R2 replay snapshots.

One episode per trading day: sell the put the put20 book would sell at 10:15
(Friday expiry nearest 30 DTE in 21-45, strike nearest 20 delta), then follow
that contract each day at 10:15 until the 7-DTE time exit. Stops and the
profit-take are applied inside training, because they depend on the hedge.
Only days before the hold-out are read.
"""
import math
from concurrent.futures import ProcessPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import deep_hedge, engine
from lsgamma.trading import runner, selection
from lsgamma.trading.sizing import put_strike

HHMM = "10:15"
KEEP = ["expiry", "strike", "dte", "mid", "iv", "delta"]


def one_day(args):
    d, root = args
    asof = engine.at(d, HHMM)
    folder = engine.store.folder(asof, root)
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
    spot = runner.spot(chain)
    fspot = math.nan if fill is None else float(fill["und_price"].median())
    entry = None
    try:
        cfg = {"entry": {"target_dte": 30, "min_dte": 21, "max_dte": 45}}
        t = selection.trade_for("short", chain, cfg)
        entry = (str(t["expiry"]), put_strike(t, chain, 0.20))
    except (ValueError, KeyError):
        pass
    return {"date": d, "spot": spot, "fspot": fspot, "entry": entry,
            "puts": puts.assign(date=d)}


def build_panel(cfg, start, end, workers=12):
    root = engine.snapshots(cfg)
    feats = pd.read_parquet(root / "features.parquet")
    days = engine.trading_days(feats, start, end)
    with ProcessPoolExecutor(workers) as ex:
        out = [r for r in ex.map(one_day, [(d, root) for d in days], chunksize=20) if r]
    daily = pd.DataFrame([{k: r[k] for k in ("date", "spot", "fspot")} | {
        "entry_expiry": r["entry"][0] if r["entry"] else None,
        "entry_strike": r["entry"][1] if r["entry"] else math.nan} for r in out])
    puts = pd.concat([r["puts"] for r in out], ignore_index=True)
    puts["expiry"] = puts["expiry"].astype(str)
    mkt = pd.DataFrame([deep_hedge.market(runner.completed(feats, engine.at(d, HHMM)))
                        for d in daily["date"]])
    return pd.concat([daily, mkt], axis=1), puts


def episodes(daily, puts, end_cut):
    """Arrays for episodes whose time exit is before end_cut (no leakage).

    Per step k: decision spot S, fill spot F, decision mark M, close price at
    the fill ask (C), |delta|, and the eight static features. Steps where the
    contract has no row are marked invalid (the engine skips them too).
    """
    daily = daily.reset_index(drop=True)
    pos = {d: i for i, d in enumerate(daily["date"])}
    key = puts.set_index(["date", "expiry", "strike"]).sort_index()
    eps = []
    for i, r in daily.iterrows():
        if r["entry_expiry"] is None or math.isnan(r["entry_strike"]):
            continue
        exp = date.fromisoformat(r["entry_expiry"])
        days = [d for d in daily["date"].iloc[i:] if d <= exp]
        exit_day = next((d for d in days if (exp - d).days <= 7), None)
        if exit_day is None or exit_day >= end_cut:
            continue
        steps = []
        for d in days[:days.index(exit_day) + 1]:
            j = pos[d]
            try:
                row = key.loc[(d, r["entry_expiry"], r["entry_strike"])]
            except KeyError:
                row = None
            dl = daily.iloc[j]
            steps.append({"date": d, "S": dl["spot"], "F": dl["fspot"], "K": r["entry_strike"],
                          "M": math.nan if row is None else row["mid"],
                          "C": math.nan if row is None else row["f_ask"],
                          "O": math.nan if row is None else row["f_bid"],
                          "ad": math.nan if row is None else abs(row["delta"]),
                          "iv": math.nan if row is None else row["iv"],
                          "left": (exp - d).days,
                          **{k: dl[k] for k in ("vix", "vix_vix3m", "rv20", "ret5", "ret20")}})
        st = pd.DataFrame(steps)
        if st.iloc[0][["O", "F", "ad"]].isna().any():
            continue  # no entry fill: the engine would not open
        eps.append({"entry": r["date"], "exit": exit_day, "steps": st})
    return eps


def tensors(eps):
    """Padded arrays: [episode, step]."""
    n, L = len(eps), max(len(e["steps"]) for e in eps)
    nan = np.full((n, L), np.nan)
    A = {k: nan.copy() for k in ("S", "F", "M", "C", "ad", "left")}
    X = np.full((n, L, len(deep_hedge.FEATURES) - 1), np.nan)
    last = np.zeros(n, dtype=int)
    P0 = np.zeros(n)
    for i, e in enumerate(eps):
        st = e["steps"]
        m = len(st)
        for k in A:
            A[k][i, :m] = st[k].to_numpy(float)
        # entry fill at the 1x fill-view bid, as the engine
        P0[i] = max(float(st["O"].iloc[0]), 0.01)  # engine floors fills at one tick
        for k in range(m):
            row = st.iloc[k]
            mkt = {c: row[c] for c in ("vix", "vix_vix3m", "rv20", "ret5", "ret20")}
            X[i, k] = deep_hedge.features(row["ad"], row["left"], row["iv"], mkt, 0.0)[:-1]
        last[i] = m - 1
        # contract gone from the chain at exit (far OTM): the engine settles it
        # at intrinsic, as here
        for k, ref in (("C", "F"), ("M", "S")):
            if np.isnan(A[k][i, m - 1]):
                A[k][i, m - 1] = max(float(st["K"].iloc[0]) - A[ref][i, m - 1], 0.0)
    valid = ~np.isnan(A["ad"]) & ~np.isnan(A["F"]) & ~np.isnan(A["M"])
    return {**A, "X": X, "P0": P0, "last": last, "valid": valid}


def save_panel(name, daily, puts):
    folder = experiments.ROOT / name
    folder.mkdir(parents=True, exist_ok=True)
    daily.to_parquet(folder / "panel_daily.parquet")
    puts.to_parquet(folder / "panel_puts.parquet")
    return folder


def load_panel(name):
    folder = experiments.ROOT / name
    return (pd.read_parquet(folder / "panel_daily.parquet"),
            pd.read_parquet(folder / "panel_puts.parquet"))
