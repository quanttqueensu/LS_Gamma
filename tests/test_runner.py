from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lsgamma.trading import config, ledger, runner

DAY1, DAY2 = date(2026, 10, 1), date(2026, 10, 2)
SPOT = 600.0


class FakeTrade:
    def __init__(self, contract, order, price):
        self.contract, self.order = contract, order
        self.orderStatus = SimpleNamespace(status="Filled", filled=order.totalQuantity,
                                           avgFillPrice=price)

    def isDone(self):
        return True


class FakeIB:
    def __init__(self):
        self.book, self.orders = {}, []

    def qualifyContracts(self, *cs):
        for c in cs:
            c.conId = 1
        return cs

    def reqMktData(self, c, *a):
        delta = 0.5 if getattr(c, "right", "") == "C" else -0.5
        return SimpleNamespace(contract=c, midpoint=lambda: 5.0, marketPrice=lambda: 5.0,
                               modelGreeks=SimpleNamespace(delta=delta))

    def cancelMktData(self, c):
        pass

    def sleep(self, s):
        pass

    def cancelOrder(self, o):
        pass

    def placeOrder(self, contract, order):
        sign = 1 if order.action == "BUY" else -1
        key = (contract.secType, getattr(contract, "right", ""), getattr(contract, "strike", 0))
        c = self.book.get(key, (contract, 0))[0]
        self.book[key] = (c, self.book.get(key, (c, 0))[1] + sign * order.totalQuantity)
        self.orders.append((contract.secType, order.action, order.totalQuantity))
        price = order.lmtPrice if contract.secType == "OPT" else SPOT
        return FakeTrade(contract, order, price)

    def positions(self):
        return [SimpleNamespace(contract=c, position=q) for c, q in self.book.values() if q]


def snapshot():
    rng = np.random.default_rng(0)
    feats = pd.DataFrame({"ret": rng.normal(0, 0.01, 500)})
    rows = []
    for expiry in (date(2026, 10, 2), date(2026, 10, 30), date(2026, 11, 6)):
        for strike in (595.0, 600.0, 605.0):
            for right in ("C", "P"):
                rows.append({"expiry": expiry, "dte": (expiry - DAY1).days, "strike": strike,
                             "right": right, "mid": 5.0, "iv": 0.15, "und_price": SPOT})
    chain = pd.DataFrame(rows)
    atm = pd.DataFrame({"expiry": [date(2026, 10, 30)], "dte": [29],
                        "strike": [600.0], "atm_iv": [0.15]})
    return {"features": feats, "chain": chain, "atm_iv": atm}


class Fixed:
    vol = 0.0

    def fit(self, returns):
        return self

    def predict(self, horizon):
        return Fixed.vol


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "ROOT", tmp_path)
    data = snapshot()
    monkeypatch.setattr(runner.store, "load", lambda name: data[name])
    monkeypatch.setitem(runner.FORECASTERS, "fixed", Fixed)
    cfg = config.load()
    cfg["signal"]["forecaster"] = "fixed"
    return cfg


def test_dry_run_places_nothing(env):
    Fixed.vol = 0.10
    d = runner.run(None, env, DAY1, dry=True)
    assert d["signal"] == "short"
    assert ledger.load_position() is None
    assert ledger.read_log("signals").empty


def test_open_hedge_then_flip(env):
    ib = FakeIB()
    Fixed.vol = 0.10
    runner.run(ib, env, DAY1)
    pos = ledger.load_position()
    assert pos["side"] == "short" and pos["right"] == "P" and pos["strike"] == 600.0
    assert pos["expiry"] == "2026-10-30"
    assert pos["hedges"][0]["shares"] == -50

    Fixed.vol = 0.25
    runner.run(ib, env, DAY2)
    pos = ledger.load_position()
    assert pos["side"] == "long" and pos["right"] == "C"
    trades = ledger.read_log("trades")
    assert trades["action"].tolist() == ["open", "close", "open"]
    assert trades["reason"].iloc[1] == "flip"
    assert len(ledger.read_log("signals")) == 2


def test_flat_signal_no_trade(env):
    ib = FakeIB()
    Fixed.vol = 0.16
    d = runner.run(ib, env, DAY1)
    assert d["signal"] == "flat"
    assert ledger.load_position() is None
    assert ib.orders == []


def test_missing_greeks_skips_run(env, monkeypatch):
    data = snapshot()
    data["chain"]["iv"] = float("nan")
    monkeypatch.setattr(runner.store, "load", lambda name: data[name])
    with pytest.raises(runner.BadSnapshot):
        runner.run(FakeIB(), env, DAY1)
    assert ledger.read_log("signals").empty


def test_missing_atm_iv_skips_run(env, monkeypatch):
    data = snapshot()
    data["atm_iv"]["atm_iv"] = float("nan")
    monkeypatch.setattr(runner.store, "load", lambda name: data[name])
    with pytest.raises(runner.BadSnapshot):
        runner.run(FakeIB(), env, DAY1)
