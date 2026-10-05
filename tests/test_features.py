import math
from datetime import date

import pandas as pd

from lsgamma.pipeline.features import atm_iv


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
