from pathlib import Path

import numpy as np
import pandas as pd

from Data.pipeline import black76 as b76
from Data.pipeline import smile as sm

MAX_RMSE = 0.05
IV_MIN = 0.02
IV_MAX = 3.0

PRINT = "print"
FALLBACK = "model_fallback"
MODEL = "model"
MODES = (PRINT, FALLBACK, MODEL)

NONE = "none"
FLAT = "flat"


def _arrays(*vals):
    return [np.array([v], dtype=float) for v in vals]


def load_table(data_dir):
    s = pd.read_parquet(Path(data_dir) / "surface" / "smile_params.parquet")
    f = pd.read_parquet(Path(data_dir) / "chain" / "forwards_daily.parquet",
                        columns=["date", "expiry", "r"])
    for df in (s, f):
        df["date"] = pd.to_datetime(df["date"].to_numpy())
        df["expiry"] = pd.to_datetime(df["expiry"].to_numpy())
    return s.merge(f, on=["date", "expiry"], how="left")


class SmilePricer:
    def __init__(self, data_dir, max_rmse=MAX_RMSE, extrapolate=FLAT):
        t = load_table(data_dir)
        self.extrapolate = extrapolate
        # forwards are kept separate from smile fits so the intrinsic floor
        # still works on days where the fit failed or was never produced
        self._fwd = {
            (d, e): (F, T, r if np.isfinite(r) else 0.0)
            for d, e, F, T, r in zip(t["date"], t["expiry"], t["forward"],
                                     t["T"], t["r"]) if F > 0 and T > 0
        }
        ok = t[t["fit_ok"].fillna(False) & (t["rmse"] <= max_rmse)]
        self._smile = {
            (d, e): (np.array([p0, p1, p2], dtype=float), kmin, kmax)
            for d, e, p0, p1, p2, kmin, kmax in zip(
                ok["date"], ok["expiry"], ok["p0"], ok["p1"], ok["p2"],
                ok["k_min"], ok["k_max"])
        }

    def __len__(self):
        return len(self._smile)

    def _fit(self, date, expiry, strike):
        fwd = self._fwd.get((date, expiry))
        curve = self._smile.get((date, expiry))
        if fwd is None or curve is None or strike <= 0:
            return None
        F, T, r = fwd
        params, k_min, k_max = curve
        k = float(np.log(strike / F))
        if not sm.in_range(k, k_min, k_max):
            if self.extrapolate != FLAT:
                return None
            # flat wings beyond the fitted range. the quadratic blows up out
            # there, so clamp k rather than evaluate it; the intrinsic floor
            # below carries the deep-ITM cases the smile cannot reach.
            k = min(max(k, k_min), k_max)
        iv = float(sm.evaluate(params, np.array([k]))[0])
        if not IV_MIN < iv < IV_MAX:
            return None
        return iv, F, T, r

    def intrinsic(self, date, expiry, strike, right):
        fwd = self._fwd.get((date, expiry))
        if fwd is None:
            return None
        F, T, r = fwd
        a = _arrays(F, strike, T, r)
        return float(b76.intrinsic(*a, np.array([right == "C"]))[0])

    # stage 2 stores spot delta = fwd_delta * F/S; matching it keeps the hedge
    # from jumping when a leg switches between print and model marks
    def __call__(self, date, expiry, strike, right, spot=None):
        got = self._fit(date, expiry, strike)
        if got is None:
            return None
        iv, F, T, r = got
        # black76 is written for arrays; scalars break its masked writes
        Fa, Ka, Ta, va, ra = _arrays(F, strike, T, iv, r)
        ca = np.array([right == "C"])
        px = float(b76.price(Fa, Ka, Ta, va, ra, ca)[0])
        fwd_delta = float(b76.greeks(Fa, Ka, Ta, va, ra, ca)["fwd_delta"][0])
        delta = fwd_delta * (F / spot if spot and spot > 0 else 1.0)
        if not (np.isfinite(px) and np.isfinite(delta)):
            return None
        floor = self.intrinsic(date, expiry, strike, right)
        if floor is not None and np.isfinite(floor):
            px = max(px, floor)
        return px, delta
