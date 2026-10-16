import numpy as np
import pandas as pd
from scipy.special import ndtr

from lsgamma.history import spread
from lsgamma.pipeline.chain import COLUMNS

TZ = "America/New_York"
CLOSE = pd.Timedelta(hours=16)
YEAR = 365 * 86400
LO, HI, ITERS = 1e-3, 5.0, 60  # IV bisection bounds and steps
SMILE = ["a0", "a1", "a2", "kmin", "kmax", "n"]


def closes(expiry):
    e = pd.Series(np.atleast_1d(np.asarray(expiry, dtype=object)))
    u = {d: pd.Timestamp(d).tz_localize(TZ) + CLOSE for d in e.unique()}
    return pd.DatetimeIndex(e.map(u), tz=TZ)


def years(ts, expiry):
    ts = ts if isinstance(ts, pd.Timestamp) else pd.DatetimeIndex(ts)
    return np.asarray((closes(expiry) - ts).total_seconds()) / YEAR


def _d(F, K, T, sigma):
    v = sigma * np.sqrt(T)
    d1 = (np.log(F / K) + 0.5 * v * v) / v
    return d1, d1 - v


def price(F, K, T, r, sigma, call):
    with np.errstate(all="ignore"):
        d1, d2 = _d(F, K, T, sigma)
        c = F * ndtr(d1) - K * ndtr(d2)
        p = K * ndtr(-d2) - F * ndtr(-d1)
        return np.exp(-r * T) * np.where(call, c, p)


def implied(px, F, K, T, r, call):
    px, F, K, T, call = np.broadcast_arrays(*map(np.asarray, (px, F, K, T, call)))
    with np.errstate(all="ignore"):
        disc = np.exp(-r * T)
        floor = disc * np.maximum(np.where(call, F - K, K - F), 0)
        ok = (px > price(F, K, T, r, LO, call)) & (px < price(F, K, T, r, HI, call))
        ok &= (px > floor) & (T > 0)
    lo, hi = np.full(px.shape, LO), np.full(px.shape, HI)
    for _ in range(ITERS):
        mid = 0.5 * (lo + hi)
        high = price(F, K, T, r, mid, call) > px
        hi, lo = np.where(high, mid, hi), np.where(high, lo, mid)
    return np.where(ok, 0.5 * (lo + hi), np.nan)


def greeks(F, K, T, r, sigma, call):
    # IBKR units: share, vol point, day
    with np.errstate(all="ignore"):
        d1, d2 = _d(F, K, T, sigma)
        disc = np.exp(-r * T)
        S, sq = F * disc, np.sqrt(T)
        pdf = np.exp(-0.5 * d1 * d1) / np.sqrt(2 * np.pi)
        carry = np.where(call, r * K * disc * ndtr(d2), -r * K * disc * ndtr(-d2))
        return {"delta": np.where(call, ndtr(d1), ndtr(d1) - 1),
                "gamma": pdf / (S * sigma * sq),
                "vega": S * pdf * sq / 100,
                "theta": (-S * pdf * sigma / (2 * sq) - carry) / 365}


def trade_ivs(tr, fwd, r):
    T = years(tr["ts"], tr["expiry"])
    call = (tr["opt_type"] == "C").to_numpy()
    iv = implied(tr["price"].to_numpy(), fwd, tr["strike"].to_numpy(), T, r, call)
    return tr.assign(k=np.log(tr["strike"].to_numpy() / fwd), iv=iv, call=call)


def _usable(g, cfg):
    return len(g) >= cfg["smile_min_trades"] and g["strike"].nunique() >= cfg["smile_min_strikes"]


def _fit(g):
    return np.polyfit(g["k"], g["iv"], 2, w=np.sqrt(g["size"].astype(float)))


def fit(g, cfg):
    g = g[g["iv"].notna() & (g["k"].abs() <= cfg["smile_k"])]
    g = g[np.where(g["call"], g["k"] >= -cfg["itm_k"], g["k"] <= cfg["itm_k"])]
    if not _usable(g, cfg):
        return None
    res = (g["iv"] - np.polyval(_fit(g), g["k"])).abs()
    g = g[res <= cfg["smile_trim"] * 1.4826 * res.median() + 1e-4]
    if not _usable(g, cfg):
        return None
    a2, a1, a0 = _fit(g)
    kmin, kmax = g["k"].min(), g["k"].max()
    if kmin > 0 or kmax < 0 or np.polyval([a2, a1, a0], np.linspace(kmin, kmax, 21)).min() <= LO:
        return None
    return {"a0": a0, "a1": a1, "a2": a2, "kmin": kmin, "kmax": kmax, "n": len(g)}


def smiles(tr, cfg):
    rows = {e: fit(g, cfg) for e, g in tr.groupby("expiry")}
    rows = {e: s for e, s in rows.items() if s is not None}
    return pd.DataFrame.from_dict(rows, orient="index", columns=SMILE)


def smile_iv(sm, expiry, k):
    s = sm.reindex(pd.Index(expiry, dtype=object)).astype(float)
    k = np.clip(k, s["kmin"].to_numpy(), s["kmax"].to_numpy())
    return s["a0"].to_numpy() + s["a1"].to_numpy() * k + s["a2"].to_numpy() * k * k


def floor(F, K, T, r, spot, call):
    # discounted or exercise-now intrinsic, whichever higher
    fwd = np.exp(-r * T) * np.where(call, F - K, K - F)
    now = np.where(call, spot - K, K - spot)
    return np.maximum(np.maximum(fwd, now), 0.0)


def chain(universe, fwd, sm, asof, r, spot, model):
    u = universe.reset_index(drop=True)
    K = u["strike"].to_numpy(dtype=float)
    T = years(asof, u["expiry"])
    k = np.log(K / fwd)
    iv = smile_iv(sm, u["expiry"], k)
    call = (u["right"] == "C").to_numpy()
    mid = np.maximum(price(fwd, K, T, r, iv, call), floor(fwd, K, T, r, spot, call))
    dte = np.array([(e - asof.date()).days for e in u["expiry"]])
    g = greeks(fwd, K, T, r, iv, call)
    half = spread.half_spread(mid, dte, model, delta=g["delta"])
    df = pd.DataFrame({"asof": asof, "expiry": u["expiry"], "dte": dte, "strike": K,
                       "right": u["right"], "bid": mid - half, "ask": mid + half,
                       "mid": mid, "iv": iv, **g, "und_price": spot})
    return df[COLUMNS].sort_values(["expiry", "strike", "right"]).reset_index(drop=True)
