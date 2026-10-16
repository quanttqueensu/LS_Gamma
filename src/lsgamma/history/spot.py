import numpy as np
import pandas as pd

from lsgamma.history import marks, trades

COLS = ["ts", "expiry", "strike", "price"]
NO_DIVS = pd.Series(dtype=float, index=pd.Index([], dtype=object))


def ns(ts):
    return pd.DatetimeIndex(ts).as_unit("ns")


def _last(left, right, tol):
    right = right.rename(columns={"price": "other", "ts": "ts_other"})
    right["ts"] = right["ts_other"]
    return pd.merge_asof(left, right[["ts", "expiry", "strike", "other"]], on="ts",
                         by=["expiry", "strike"], tolerance=tol, direction="backward")


def pairs(tr, r, cfg):
    # each print pairs with the latest opposite print
    tol = pd.Timedelta(seconds=cfg["pair_secs"])
    tr = tr[COLS + ["opt_type"]].assign(ts=ns(tr["ts"])).sort_values("ts", kind="stable")
    c, p = (tr.loc[tr["opt_type"] == x, COLS] for x in "CP")
    a, b = _last(p, c, tol), _last(c, p, tol)
    cp = pd.concat([a.assign(cp=a["other"] - a["price"]), b.assign(cp=b["price"] - b["other"])])
    cp = cp.dropna(subset=["cp"]).sort_values("ts", kind="stable").reset_index(drop=True)
    cp["fwd"] = cp["strike"] + cp["cp"] * np.exp(r * marks.years(cp["ts"], cp["expiry"]))
    return cp[["ts", "expiry", "strike", "fwd"]]


def _roll(x, n, m):
    return x.rolling(n, min_periods=m).median()


def near_expiry(prs, day, need):
    n = prs.groupby("expiry").size()
    n = n[(n.index >= day) & (n >= need)]
    return min(n.index) if len(n) else None


def near_forward(prs, near, cfg):
    g = prs[prs["expiry"] == near]
    rough = _roll(g["fwd"], cfg["fwd_pairs"], 1)
    g = g[(g["strike"] / rough - 1).abs() <= cfg["fwd_band"]]
    f = _roll(g["fwd"], cfg["fwd_pairs"], cfg["min_pairs"])
    return pd.DataFrame({"ts": g["ts"], "fnear": f}).dropna().reset_index(drop=True)


def _with_near(df, fw):
    return pd.merge_asof(df, fw["f"], on="ts", direction="backward")


def _carry(df, fw):
    # forward implied by spot, without parity
    tn = marks.years(df["ts"], [fw["near"]] * len(df))
    te = marks.years(df["ts"], df["expiry"])
    d = {e: divs_between(fw["divs"], fw["near"], e) for e in df["expiry"].unique()}
    d = df["expiry"].map(d).to_numpy(float)
    spot = df["fnear"].to_numpy() * np.exp(-fw["r"] * tn) - d
    return spot * np.exp(fw["r"] * te) / df["fnear"].to_numpy()


def ratios(prs, fw, cfg):
    o = _with_near(prs[prs["expiry"] != fw["near"]], fw).dropna(subset=["fnear"])
    ref = o["fnear"] * _carry(o, fw)
    o = o[(o["strike"] / ref - 1).abs() <= cfg["fwd_band"]]
    ratio = (o["fwd"] / o["fnear"]).groupby(o["expiry"]).transform(
        lambda x: _roll(x, cfg["fwd_pairs"], cfg["min_pairs"]))
    return o[["ts", "expiry"]].assign(ratio=ratio).dropna().reset_index(drop=True)


def divs_between(divs, a, b):
    return float(divs[(divs.index > a) & (divs.index <= b)].sum())


def forwards(tr, r, divs, day, cfg, need=None):
    need = need or cfg["fwd_pairs"]
    cfg = {**cfg, "min_pairs": min(cfg["min_pairs"], need)}
    prs = pairs(tr, r, cfg)
    near = near_expiry(prs, day, need)
    if near is None:
        return None
    fw = {"near": near, "r": r, "divs": divs, "f": near_forward(prs, near, cfg)}
    if fw["f"].empty:
        return None
    fw["ratios"] = ratios(prs, fw, cfg)
    return fw


def forward_at(fw, ts, expiry):
    df = pd.DataFrame({"ts": ns(ts), "expiry": np.asarray(expiry, dtype=object)})
    df["i"] = np.arange(len(df))
    df = _with_near(df.sort_values("ts", kind="stable"), fw)
    df = pd.merge_asof(df, fw["ratios"], on="ts", by="expiry", direction="backward")
    df.loc[df["expiry"] == fw["near"], "ratio"] = 1.0
    df["ratio"] = df["ratio"].fillna(pd.Series(_carry(df, fw), index=df.index))
    df = df.sort_values("i")
    return (df["fnear"] * df["ratio"]).to_numpy()


def spot(fw, t):
    f = fw["f"].loc[fw["f"]["ts"] <= t, "fnear"]
    if f.empty:
        return np.nan
    tn = marks.years(t, [fw["near"]])[0]
    return float(f.iloc[-1] * np.exp(-fw["r"] * tn) - divs_between(fw["divs"], t.date(), fw["near"]))


def parity_close(day_trades, day, r, cfg):
    day = pd.Timestamp(day).date()
    end = trades.at(day, "16:00")
    tr = trades.window(day_trades, trades.at(day, "15:45"), end, cfg)
    fw = forwards(tr, r, NO_DIVS, day, cfg)
    return np.nan if fw is None else spot(fw, end)
