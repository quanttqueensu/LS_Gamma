"""Research only: deep hedger inference for the backtest engine.

A small MLP ensemble maps nine features to a hedge ratio in [0, MAX_RATIO]:
the share of the short put's delta to hedge. Weights are trained offline,
walk-forward by year (research/Deep_Hedging/2026-11-17-deep-hedger), and
stored as JSON; a year with no model hedges full delta (ratio 1).
Training imports `features` and `market` from here so both sides match.
"""
import json
import math

import numpy as np

MAX_RATIO = 1.5
FEATURES = ["abs_delta", "tau", "iv", "vix", "vix_vix3m", "rv20", "ret5", "ret20", "pnl_frac"]
DAYS = 252


def market(done):
    # daily inputs from completed days only
    ret = done["ret"].dropna()
    last = done.iloc[-1]
    return {"vix": float(last["vix"]) / 100.0, "vix_vix3m": float(last["vix_vix3m"]),
            "rv20": float(ret.iloc[-20:].std() * math.sqrt(DAYS)),
            "ret5": float(ret.iloc[-5:].sum()), "ret20": float(ret.iloc[-20:].sum())}


def features(abs_delta, days_left, iv, mkt, pnl_frac):
    return np.array([abs_delta, days_left / 30.0, iv, mkt["vix"], mkt["vix_vix3m"], mkt["rv20"],
                     mkt["ret5"], mkt["ret20"], pnl_frac], dtype=float)


def forward(net, x):
    # one member: tanh MLP, sigmoid head
    h = (x - np.asarray(net["mu"])) / np.asarray(net["sd"])
    for w, b in net["layers"][:-1]:
        h = np.tanh(h @ np.asarray(w) + np.asarray(b))
    w, b = net["layers"][-1]
    z = float((h @ np.asarray(w) + np.asarray(b))[0])
    return MAX_RATIO / (1.0 + math.exp(-z))


def ratio(model, x):
    # ensemble mean; constant models carry "const"
    if "const" in model:
        return float(model["const"])
    if np.isnan(x).any():
        return 1.0
    return float(np.mean([forward(n, x) for n in model["members"]]))


def load(path):
    with open(path) as f:
        return {int(y): m for y, m in json.load(f)["years"].items()}
