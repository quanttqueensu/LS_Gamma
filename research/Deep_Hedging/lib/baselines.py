"""Hull & White (2017) minimum-variance delta for SPY puts, fitted walk-forward.

delta_MV = delta + vega / (S * sqrt(T)) * (a + b*delta + c*delta^2), with vega per 1.00 of vol.
"""
from datetime import date

import numpy as np
import pandas as pd

MAX_GAP = 5  # calendar days between consecutive panel days


def pairs(daily, puts, cut):
    """Same-contract observations on consecutive panel days d1 < d2 < cut."""
    days = daily[["date", "spot"]].sort_values("date").reset_index(drop=True)
    days = days.assign(d2=days["date"].shift(-1), spot2=days["spot"].shift(-1)).dropna()
    gap = (pd.to_datetime(days["d2"]) - pd.to_datetime(days["date"])).dt.days
    days = days[(gap <= MAX_GAP) & (days["d2"] < cut)]
    p1 = puts.merge(days, on="date")
    p1 = p1[p1["delta"].abs().between(0.05, 0.95) & (p1["dte"] >= 7) & (p1["mid"] >= 0.05)
            & np.isfinite(p1[["vega", "delta", "iv"]]).all(axis=1)]
    p2 = puts[["date", "expiry", "strike", "mid"]].rename(columns={"date": "d2", "mid": "mid2"})
    return p1.merge(p2, on=["d2", "expiry", "strike"])


def fit_hw(daily, puts, cut):
    p = pairs(daily, puts, cut)
    d, dS, S = p["delta"].to_numpy(), (p["spot2"] - p["spot"]).to_numpy(), p["spot"].to_numpy()
    y = (p["mid2"] - p["mid"]).to_numpy() - d * dS
    k = p["vega"].to_numpy() * 100 / np.sqrt(p["dte"].to_numpy() / 365) * dS / S
    X = np.column_stack([k, k * d, k * d * d])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    gain = 1 - np.sum((y - X @ coef) ** 2) / np.sum(y ** 2)
    a, b, c = coef
    return {"a": a, "b": b, "c": c, "n": len(y), "r2_gain": gain}


def hw_delta(coef, delta, vega, spot, years):
    poly = coef["a"] + coef["b"] * delta + coef["c"] * delta ** 2
    return delta + vega * 100 / (spot * np.sqrt(years)) * poly


def hw_ratio(coef, delta, vega, spot, years, lo=0.8, hi=1.2):
    delta, vega, spot, years = np.broadcast_arrays(*map(np.asarray, (delta, vega, spot, years)))
    ok = np.isfinite(delta) & np.isfinite(vega) & np.isfinite(spot) & np.isfinite(years) \
        & (np.abs(delta) >= 1e-4) & (spot > 0) & (years > 0)
    with np.errstate(all="ignore"):
        r = np.clip(hw_delta(coef, delta, vega, spot, years) / delta, lo, hi)
    out = np.where(ok, r, 1.0)
    return out.item() if out.ndim == 0 else out


def fit_walk_forward(daily, puts, years=range(2017, 2025)):
    return {y: fit_hw(daily, puts, date(y, 1, 1)) for y in years}
