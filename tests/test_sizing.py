import math

import numpy as np
import pandas as pd

from lsgamma.backtest import config, engine
from lsgamma.trading import sizing
from test_backtest import chain

ASOF = pd.Timestamp("2024-03-04 10:15", tz="America/New_York")


def skewed():
    # put deltas fall away from the money
    c = chain(ASOF)
    return c.assign(delta=np.where(c["right"] == "P", -(c["strike"] - 590) / 20, c["delta"]))


def trade(right="P", strike=600.0):
    e = sorted({x for x in chain(ASOF)["expiry"] if 21 <= (x - ASOF.date()).days <= 45})[0]
    return {"right": right, "strike": strike, "expiry": e}


def test_put_strike_by_delta():
    c = skewed()
    assert sizing.put_strike(trade(), c, 0.25) == 595.0
    assert sizing.put_strike(trade(), c, 0.0) == 600.0
    assert sizing.put_strike(trade("C"), c, 0.25) == 600.0


def test_put_strike_skips_rows_without_delta():
    c = skewed()
    c.loc[(c["right"] == "P") & (c["strike"] == 595.0), "delta"] = math.nan
    assert sizing.put_strike(trade(), c, 0.25) == 600.0


def test_contracts_default_and_long_use_quantity():
    paper = config.read(config.CONFIGS / "paper.toml")
    assert sizing.contracts(paper, "short", trade(), chain(ASOF), ASOF) == paper["size"]["quantity"]
    book = config.variant("2026-11-02-lower-delta", "put20")
    assert sizing.contracts(book, "long", trade("C"), chain(ASOF), ASOF) == book["size"]["quantity"]


def test_contracts_missing_row_is_zero():
    book = config.variant("2026-11-02-lower-delta", "put20")
    assert sizing.contracts(book, "short", trade(strike=1.0), chain(ASOF), ASOF) == 0


def test_engine_uses_shared_sizing():
    assert engine.stress_qty is sizing.stress_qty and engine.put_strike is sizing.put_strike
