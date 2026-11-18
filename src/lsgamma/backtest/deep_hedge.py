"""Research only: deep hedger inference for the backtest engine.

A model maps the morning's inputs to a hedge ratio: the share of the short
put's delta to hedge. Models are trained offline, walk-forward by year
(research/Deep_Hedging/), and stored as JSON {"years": {year: model}}; a year
with no model hedges full delta (ratio 1). Model kinds:
- v1 (no "kind"): MLP ensemble on FEATURES, ratio in [0, 1.5]
- "net": MLP or linear ensemble on its own "features" list, ratio in [lo, hi]
- "hw": Hull-White minimum-variance delta, ratio clipped to [lo, hi]
- "const": one ratio
Training imports `market`, `features` and `inputs` from here so both sides match.
"""
import json
import math

import numpy as np

MAX_RATIO = 1.5  # v1 head
FEATURES = ["abs_delta", "tau", "iv", "vix", "vix_vix3m", "rv20", "ret5", "ret20", "pnl_frac"]
V2 = FEATURES + ["hold_frac", "vega_s"]
DAYS = 252


def market(done):
    # daily inputs from completed days only
    ret = done["ret"].dropna()
    last = done.iloc[-1]
    return {"vix": float(last["vix"]) / 100.0, "vix_vix3m": float(last["vix_vix3m"]),
            "rv20": float(ret.iloc[-20:].std() * math.sqrt(DAYS)),
            "ret5": float(ret.iloc[-5:].sum()), "ret20": float(ret.iloc[-20:].sum())}


def features(abs_delta, days_left, iv, mkt, pnl_frac):
    # v1 input vector
    return np.array([abs_delta, days_left / 30.0, iv, mkt["vix"], mkt["vix_vix3m"], mkt["rv20"],
                     mkt["ret5"], mkt["ret20"], pnl_frac], dtype=float)


def inputs(delta, days_left, iv, vega, spot, mkt, pnl_frac, hold_frac):
    # every named input any model kind uses; vega per vol point
    return {"abs_delta": abs(delta), "tau": days_left / 30.0, "iv": iv, **mkt,
            "pnl_frac": pnl_frac, "hold_frac": hold_frac, "vega_s": 100.0 * vega / spot,
            "delta": delta, "vega": vega, "spot": spot, "years": days_left / 365.0}


def forward(net, x, lo=0.0, hi=MAX_RATIO):
    # one member: tanh MLP (or linear), sigmoid head scaled to [lo, hi]
    h = (x - np.asarray(net["mu"])) / np.asarray(net["sd"])
    for w, b in net["layers"][:-1]:
        h = np.tanh(h @ np.asarray(w) + np.asarray(b))
    w, b = net["layers"][-1]
    z = float((h @ np.asarray(w) + np.asarray(b))[0])
    return lo + (hi - lo) / (1.0 + math.exp(-z))


def hw_ratio(coef, d):
    # Hull-White 2017: delta + vega/(S sqrt T) (a + b delta + c delta^2)
    a, b, c = coef
    delta = d["delta"]
    if abs(delta) < 1e-4 or not all(math.isfinite(d[k]) for k in ("delta", "vega", "spot", "years")) \
            or d["years"] <= 0:
        return 1.0
    mv = delta + 100.0 * d["vega"] / (d["spot"] * math.sqrt(d["years"])) * (a + b * delta + c * delta ** 2)
    return mv / delta


def ratio(model, x):
    # x: v1 array, or the dict from inputs()
    if "const" in model:
        return float(model["const"])
    kind = model.get("kind")
    if kind == "hw":
        return float(min(max(hw_ratio(model["coef"], x), model["lo"]), model["hi"]))
    names = model["features"] if kind == "net" else FEATURES
    v = np.array([x[k] for k in names], dtype=float) if isinstance(x, dict) else np.asarray(x)
    if np.isnan(v).any():
        return 1.0
    lo, hi = (model["lo"], model["hi"]) if kind == "net" else (0.0, MAX_RATIO)
    return float(np.mean([forward(n, v, lo, hi) for n in model["members"]]))


def load(path):
    with open(path) as f:
        return {int(y): m for y, m in json.load(f)["years"].items()}
