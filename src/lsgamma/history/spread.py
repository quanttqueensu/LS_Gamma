import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
LIVE = ROOT / "data" / "live"
CONFIG = ROOT / "configs" / "backtest_spread.toml"
FLOOR = 0.005  # half a penny tick
MAX_DTE = [14, 30, 60]  # bucket upper edges
OPEN, CLOSE = "09:45", "15:45"  # ET market-hours window
MIN_IV_COVERAGE = 0.5  # after-hours snapshots lack IV
TIERS = [0.8, 0.9]  # |delta| above each: own deep ITM fit
MIN_QUOTES = 200  # fewer per bucket: pool DTE
METHOD = "ols"  # expected cost: mean
TIER_METHOD = "ols"  # bimodal deep tiers: mean cost


def quotes(root=LIVE):
    paths = sorted([*root.glob("*/chain.parquet"), *root.glob("*/*/chain.parquet")])
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


def clean(chain):
    t = chain["asof"].dt.strftime("%H:%M")
    coverage = chain["iv"].notna().groupby(chain["asof"]).transform("mean")
    keep = ((t >= OPEN) & (t <= CLOSE) & (coverage >= MIN_IV_COVERAGE)
            & (chain["bid"] > 0) & (chain["ask"] > chain["bid"])
            & chain["delta"].notna())
    out = chain[keep].copy()
    out["half"] = (out["ask"] - out["bid"]) / 2
    out["mid"] = (out["ask"] + out["bid"]) / 2
    out["tier"] = tier(out["delta"])
    return out


def bucket(dte, edges=MAX_DTE):
    return np.searchsorted(edges[:-1], np.asarray(dte), side="left")


def tier(delta, edges=TIERS):
    return np.searchsorted(edges, np.abs(np.asarray(delta, dtype=float)), side="left")


def lad(x, y, iters=50):
    X = np.column_stack([np.ones(len(x)), x])
    w = np.ones(len(x))
    for _ in range(iters):
        coef = np.linalg.lstsq(X * w[:, None] ** 0.5, y * w ** 0.5, rcond=None)[0]
        w = 1 / np.maximum(np.abs(y - X @ coef), 1e-4)
    return coef


def ols(x, y):
    X = np.column_stack([np.ones(len(x)), x])
    return np.linalg.lstsq(X, y, rcond=None)[0]


def _row(g, edge, method):
    a, slope = {"lad": lad, "ols": ols}[method](g["mid"].to_numpy(), g["half"].to_numpy())
    return {"max_dte": edge, "a": float(a), "b": float(slope), "n": len(g)}


def fit_buckets(q, method=METHOD):
    b = bucket(q["dte"])
    if min((b == i).sum() for i in range(len(MAX_DTE))) < MIN_QUOTES:
        return [_row(q, MAX_DTE[-1], method)]
    return [_row(q[b == i], edge, method) for i, edge in enumerate(MAX_DTE)]


def fit(chain):
    q = clean(chain)
    tiers = [{"min_delta": d, "method": TIER_METHOD,
              "bucket": fit_buckets(q[q["tier"] == i], TIER_METHOD)}
             for i, d in enumerate(TIERS, 1)]
    model = {"floor": FLOOR, "method": METHOD, "bucket": fit_buckets(q[q["tier"] == 0]), "tier": tiers,
             "n_quotes": len(q), "snapshots": int(q["asof"].nunique()),
             "first": str(q["asof"].min().date()), "last": str(q["asof"].max().date())}
    return model, q


def _lookup(mid, dte, rows, floor):
    i = bucket(dte, [r["max_dte"] for r in rows]).clip(max=len(rows) - 1)
    a = np.array([r["a"] for r in rows])[i]
    b = np.array([r["b"] for r in rows])[i]
    return np.maximum(floor, a + b * np.asarray(mid, dtype=float))


def tiers(model):
    out = list(model.get("tier", []))
    if "deep_bucket" in model:  # older single deep-ITM files
        out.append({"min_delta": model["deep_delta"], "bucket": model["deep_bucket"]})
    return sorted(out, key=lambda t: t["min_delta"])


def half_spread(mid, dte, model, delta=None):
    out = _lookup(mid, dte, model["bucket"], model["floor"])
    if delta is None:
        return out
    absd = np.abs(np.asarray(delta, dtype=float))
    for t in tiers(model):
        out = np.where(absd > t["min_delta"], _lookup(mid, dte, t["bucket"], model["floor"]), out)
    return out


def quality(model, q):
    err = (half_spread(q["mid"], q["dte"], model, q["delta"]) - q["half"]).abs()
    keys = [q["tier"].rename("tier"), pd.Series(bucket(q["dte"]), q.index, name="bucket")]
    fitted = half_spread(q["mid"], q["dte"], model, q["delta"])
    df = pd.DataFrame({"half": q["half"], "fitted": fitted, "err": err})
    return df.groupby(keys).agg(
        n=("half", "size"), mean_half=("half", "mean"), mean_fitted=("fitted", "mean"),
        median_half=("half", "median"), median_abs_err=("err", "median"))


def _table(name, rows):
    out = []
    for r in rows:
        out += ["", f"[[{name}]]", f"max_dte = {r['max_dte']}", f"a = {r['a']:.6f}",
                f"b = {r['b']:.6f}", f"n = {r['n']}"]
    return out


def save(model, path=CONFIG):
    lines = ["# Half-spread fit on live IBKR quotes (lsgamma.history.spread).",
             "# half = max(floor, a + b * mid), USD/share, by DTE.",
             "# Each tier replaces bucket when |delta| > min_delta.",
             "# Market hours only; at 1x, engine applies spread_mult.",
             f"floor = {model['floor']}",
             f'method = "{model["method"]}"',
             f"n_quotes = {model['n_quotes']}",
             f"snapshots = {model['snapshots']}",
             f'first = "{model["first"]}"',
             f'last = "{model["last"]}"']
    lines += _table("bucket", model["bucket"])
    for t in model["tier"]:
        lines += ["", "[[tier]]", f"min_delta = {t['min_delta']}",
                  f'method = "{t["method"]}"'] + _table("tier.bucket", t["bucket"])
    Path(path).write_text("\n".join(lines) + "\n")
    return path


def load(path=CONFIG):
    with open(path, "rb") as f:
        return tomllib.load(f)


if __name__ == "__main__":
    model, q = fit(quotes())
    save(model)
    print(f"{model['n_quotes']} quotes, {model['snapshots']} snapshots, "
          f"{model['first']} to {model['last']}")
    for name, rows in [("|delta|<=0.8", model["bucket"])] + [
            (f"|delta|>{t['min_delta']}", t["bucket"]) for t in model["tier"]]:
        for r in rows:
            print(f"{name} dte<={r['max_dte']}: a={r['a']:.4f} b={r['b']:.4f} n={r['n']}")
    print(quality(model, q).round(4).to_string())
