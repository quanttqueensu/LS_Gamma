import math
from datetime import date

import numpy as np
import pandas as pd

from lsgamma.pipeline.features import atm_iv, bad_range, log_returns, rv_gk


def bars(n=40, bad=None, shock=None):
    # 1% daily range, closes drifting up 0.1% a day
    close = pd.Series(100 * 1.001 ** np.arange(n),
                      index=pd.bdate_range("2006-01-02", periods=n))
    spy = pd.DataFrame({"open": close / 1.001, "high": close * 1.005,
                        "low": close * 0.995, "close": close})
    if bad is not None:
        spy.iloc[bad, spy.columns.get_loc("low")] = close.iloc[bad] * 0.45  # ln(H/L) ~ 0.8
    if shock is not None:
        spy.iloc[shock, spy.columns.get_loc("low")] = close.iloc[shock] * 0.90  # 11x the range
    return spy


def test_bad_low_falls_back_to_squared_return():
    spy = bars(bad=30)
    gk, flags = rv_gk(spy), bad_range(spy)
    assert flags.sum() == 1 and flags.iloc[30]
    assert gk.iloc[30] == log_returns(spy).iloc[30] ** 2
    assert np.allclose(gk.drop(gk.index[30]), rv_gk(bars()).drop(gk.index[30]))


def test_genuine_shock_is_kept():
    spy = bars(shock=30)
    assert not bad_range(spy).any()
    assert rv_gk(spy).iloc[30] > 0.005  # the wide range is used, not the 0.1% return


def chain(ivs):
    rows = [{"expiry": date(2026, 10, 30), "dte": 28, "strike": k, "right": r,
             "iv": ivs.get(k), "und_price": 770.0}
            for k in (765.0, 770.0, 795.0) for r in ("C", "P")]
    return pd.DataFrame(rows)


def test_uses_strike_nearest_spot():
    out = atm_iv(chain({765.0: 0.14, 770.0: 0.13, 795.0: 0.11}))
    assert out["strike"].iloc[0] == 770.0
    assert out["atm_iv"].iloc[0] == 0.13


def test_missing_atm_iv_is_nan_not_far_strike():
    out = atm_iv(chain({770.0: None, 795.0: 0.11}))
    assert out["strike"].iloc[0] == 770.0
    assert math.isnan(out["atm_iv"].iloc[0])
