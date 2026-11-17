import json
import math

import numpy as np
import pandas as pd

from lsgamma.backtest import deep_hedge, engine


def untrained(n=9, hidden=4):
    # zero head: ratio 1 whatever the input
    b = math.log(1 / (deep_hedge.MAX_RATIO - 1))
    return {"mu": [0.0] * n, "sd": [1.0] * n,
            "layers": [([[0.1] * hidden] * n, [0.0] * hidden), ([[0.0]] * hidden, [b])]}


def test_untrained_net_hedges_full_delta():
    x = deep_hedge.features(0.2, 20, 0.15, {"vix": 0.15, "vix_vix3m": 0.9, "rv20": 0.12,
                                             "ret5": 0.01, "ret20": 0.02}, -0.1)
    assert len(x) == len(deep_hedge.FEATURES)
    assert abs(deep_hedge.ratio({"members": [untrained()]}, x) - 1.0) < 1e-12


def test_const_and_nan_inputs():
    assert deep_hedge.ratio({"const": 0.7}, np.zeros(9)) == 0.7
    assert deep_hedge.ratio({"members": [untrained()]}, np.full(9, np.nan)) == 1.0


def test_market_uses_completed_rows():
    done = pd.DataFrame({"ret": [0.01] * 25, "vix": [20.0] * 25, "vix_vix3m": [0.9] * 25})
    m = deep_hedge.market(done)
    assert m["vix"] == 0.2 and abs(m["ret5"] - 0.05) < 1e-12 and abs(m["rv20"]) < 1e-12


def test_engine_off_by_default_and_year_gated(tmp_path, monkeypatch):
    chain = pd.DataFrame({"expiry": [pd.Timestamp("2018-02-16").date()], "strike": [260.0],
                          "right": ["P"], "delta": [-0.2], "iv": [0.15], "mid": [2.0],
                          "und_price": [270.0]})
    pos = {"side": "short", "right": "P", "expiry": "2018-02-16", "strike": 260.0, "qty": 10,
           "entry_price": 2.0, "mark": 2.0, "hedges": []}
    asof = engine.at(pd.Timestamp("2018-01-17").date(), "10:15")
    s = {"cfg": {"backtest": {}}, "events": []}
    assert engine.target(s, pos, chain, asof) == -200.0  # short 20 shares a contract
    (tmp_path / "p.json").write_text(json.dumps({"years": {"2019": {"const": 0.5}}}))
    monkeypatch.setattr(engine.experiments, "ROOT", tmp_path)
    s = {"cfg": {"backtest": {"deep_hedge": "p.json"}}, "events": []}
    assert engine.target(s, pos, chain, asof) == -200.0  # no 2018 model
    (tmp_path / "p.json").write_text(json.dumps({"years": {"2018": {"const": 0.5}}}))
    s = {"cfg": {"backtest": {"deep_hedge": "p.json"}}, "events": [],
         "feats": pd.DataFrame({"ret": [0.0] * 30, "vix": [15.0] * 30, "vix_vix3m": [0.9] * 30},
                               index=pd.bdate_range("2017-11-01", periods=30))}
    assert engine.target(s, pos, chain, asof) == -100.0
