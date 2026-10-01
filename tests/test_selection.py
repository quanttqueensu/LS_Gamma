import math
from datetime import date, timedelta

import pandas as pd
import pytest

from lsgamma.core.Algos.SG_ShortPut import short_put
from lsgamma.trading import selection

ASOF = date(2026, 9, 29)
CFG = {"entry": {"target_dte": 30, "min_dte": 21, "max_dte": 45}}


def make_chain(dtes, spot=500.0):
    rows = []
    for dte in dtes:
        for strike in [490.0, 495.0, 500.0, 505.0, 510.0]:
            for right in ["C", "P"]:
                rows.append({"asof": ASOF, "expiry": ASOF + timedelta(days=dte), "dte": dte,
                             "strike": strike, "right": right, "bid": 4.9, "ask": 5.1,
                             "mid": 5.0, "und_price": spot})
    return pd.DataFrame(rows)


def test_picks_nearest_friday():
    # Fridays at 24, 31, 38; Thursday at 30
    chain = make_chain([3, 24, 30, 31, 38, 52])
    assert selection.pick_expiry(chain, CFG) == date(2026, 10, 30)


def test_ignores_non_friday_at_target():
    chain = make_chain([24, 30])
    assert date(2026, 10, 29).weekday() == 3
    assert selection.pick_expiry(chain, CFG) == ASOF + timedelta(days=24)


def test_tie_goes_to_earlier():
    cfg = {"entry": {"target_dte": 27.5, "min_dte": 21, "max_dte": 45}}
    chain = make_chain([31, 24])
    assert selection.pick_expiry(chain, cfg) == ASOF + timedelta(days=24)


def test_empty_window_raises():
    with pytest.raises(ValueError):
        selection.pick_expiry(make_chain([3, 10, 52]), CFG)


def test_pick_strike_atm():
    chain = make_chain([31], spot=503.0)
    assert selection.pick_strike(chain, date(2026, 10, 30), "P") == 505.0


def test_pick_strike_skips_nan_mid():
    chain = make_chain([31], spot=500.0)
    chain.loc[(chain["strike"] == 500.0) & (chain["right"] == "C"), "mid"] = float("nan")
    assert selection.pick_strike(chain, "2026-10-30", "C") in (495.0, 505.0)


def test_mark():
    chain = make_chain([31])
    chain.loc[(chain["strike"] == 495.0) & (chain["right"] == "C"), "mid"] = float("nan")
    assert selection.mark(chain, "2026-10-30", 500.0, "P") == 5.0
    assert selection.mark(chain, date(2026, 10, 30), 500.0, "C") == 5.0
    assert math.isnan(selection.mark(chain, "2026-10-30", 495.0, "C"))
    assert math.isnan(selection.mark(chain, "2026-10-30", 999.0, "C"))


def test_trade_for_short():
    trade = selection.trade_for("short", make_chain([24, 30, 31, 38]), CFG)
    assert trade["right"] == "P"
    assert trade["algo"] is short_put
    assert trade["expiry"] == date(2026, 10, 30)
    assert trade["strike"] == 500.0
    assert trade["side"] == "short"
