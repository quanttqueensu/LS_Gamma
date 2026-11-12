import json
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from lsgamma.trading import config, ledger, runner

def at(day, hhmm="10:15"):
    return pd.Timestamp(f"2026-10-{day:02d} {hhmm}", tz="America/New_York")


DAY1, DAY2 = at(1), at(2)
SPOT = 600.0


class FakeTrade:
    def __init__(self, contract, order, price, filled=None):
        n = order.totalQuantity if filled is None else filled
        self.contract, self.order = contract, order
        self.orderStatus = SimpleNamespace(status="Filled" if n == order.totalQuantity else "Submitted",
                                           filled=n, avgFillPrice=price if n else 0.0)

    def isDone(self):
        return self.orderStatus.status in ("Filled", "Cancelled")


class FakeIB:
    def __init__(self, partial=None, deltas=None):
        # partial: {secType: fills for the next order}
        self.book, self.orders, self.trades = {}, [], []
        self.partial, self.deltas = dict(partial or {}), deltas or {}

    def qualifyContracts(self, *cs):
        for c in cs:
            c.conId = 1
        return cs

    def reqMktData(self, c, *a):
        right = getattr(c, "right", "")
        delta = self.deltas.get((right, getattr(c, "strike", 0)), 0.5 if right == "C" else -0.5)
        return SimpleNamespace(contract=c, midpoint=lambda: 5.0, marketPrice=lambda: 5.0,
                               modelGreeks=SimpleNamespace(delta=delta))

    def cancelMktData(self, c):
        pass

    def sleep(self, s):
        pass

    def cancelOrder(self, o):
        for t in self.trades:
            if t.order is o and t.orderStatus.status != "Filled":
                t.orderStatus.status = "Cancelled"

    def placeOrder(self, contract, order):
        sign = 1 if order.action == "BUY" else -1
        cap = self.partial.pop(contract.secType, None)
        n = order.totalQuantity if cap is None else min(cap, order.totalQuantity)
        key = (contract.secType, getattr(contract, "right", ""), getattr(contract, "strike", 0))
        c = self.book.get(key, (contract, 0))[0]
        self.book[key] = (c, self.book.get(key, (c, 0))[1] + sign * n)
        self.orders.append((contract.secType, order.action, order.totalQuantity))
        price = order.lmtPrice if contract.secType == "OPT" else SPOT
        self.trades.append(FakeTrade(contract, order, price, n))
        return self.trades[-1]

    def positions(self):
        return [SimpleNamespace(contract=c, position=q) for c, q in self.book.values() if q]


def snapshot():
    rng = np.random.default_rng(0)
    days = pd.bdate_range(end=DAY1.date(), periods=500, name="date")
    feats = pd.DataFrame({"ret": rng.normal(0, 0.01, 500)}, index=days)
    rows = []
    for expiry in (date(2026, 10, 2), date(2026, 10, 30), date(2026, 11, 6)):
        for strike in (595.0, 600.0, 605.0):
            for right in ("C", "P"):
                rows.append({"expiry": expiry, "dte": (expiry - DAY1.date()).days, "strike": strike,
                             "right": right, "mid": 5.0, "iv": 0.15, "und_price": SPOT})
    chain = pd.DataFrame(rows)
    atm = pd.DataFrame({"expiry": [date(2026, 10, 30)], "dte": [29],
                        "strike": [600.0], "atm_iv": [0.15]})
    return {"features": feats, "chain": chain, "atm_iv": atm}


class Fixed:
    vol = 0.0
    fitted = None

    def fit(self, returns):
        Fixed.fitted = returns
        return self

    def predict(self, horizon):
        return Fixed.vol


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "ROOT", tmp_path)
    data = snapshot()
    monkeypatch.setattr(runner.store, "load", lambda name, asof=None: data[name])
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
    snap = json.loads(runner.desk.OUT.read_text())
    assert snap["position"]["side"] == "long" and len(snap["signals"]) == 2
    assert [t["action"] for t in snap["trades"]] == ["open", "close", "open"]


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
    monkeypatch.setattr(runner.store, "load", lambda name, asof=None: data[name])
    with pytest.raises(runner.BadSnapshot):
        runner.run(FakeIB(), env, DAY1)
    assert ledger.read_log("signals").empty


def test_missing_atm_iv_skips_run(env, monkeypatch):
    data = snapshot()
    data["atm_iv"]["atm_iv"] = float("nan")
    monkeypatch.setattr(runner.store, "load", lambda name, asof=None: data[name])
    with pytest.raises(runner.BadSnapshot):
        runner.run(FakeIB(), env, DAY1)


def test_flat_exit_counts_days_not_runs(env):
    ib = FakeIB()
    Fixed.vol = 0.10
    runner.run(ib, env, DAY1)
    Fixed.vol = 0.16
    for hhmm in ("10:15", "11:15", "12:15", "13:15"):
        runner.run(ib, env, at(2, hhmm))
    assert ledger.load_position() is not None
    runner.run(ib, env, at(3))
    assert ledger.load_position() is not None
    runner.run(ib, env, at(4))
    assert ledger.load_position() is None
    assert ledger.read_log("trades")["reason"].iloc[-1] == "flat"


def test_rows_carry_timestamps(env):
    Fixed.vol = 0.10
    runner.run(FakeIB(), env, at(1, "11:15"))
    assert ledger.read_log("signals")["ts"].iloc[0] == "2026-10-01T11:15:00-04:00"
    assert ledger.load_position()["hedges"][0]["ts"] == "2026-10-01T11:15:00-04:00"


def test_live_rejects_intraday_schedule(env):
    runner.check_schedule(env)
    env["schedule"]["hedge"] = ["10:15", "11:15"]
    with pytest.raises(SystemExit):
        runner.check_schedule(env)


def test_forecast_skips_todays_partial_bar(env):
    Fixed.vol = 0.16
    runner.run(None, env, DAY1, dry=True)
    assert len(Fixed.fitted) == 499
    assert Fixed.fitted.index.max() < pd.Timestamp(DAY1.date())


def test_flip_carries_hedge_shares(env):
    ib = FakeIB()
    Fixed.vol = 0.10
    runner.run(ib, env, DAY1)
    Fixed.vol = 0.25
    runner.run(ib, env, DAY2)
    pos = ledger.load_position()
    assert pos["side"] == "long"
    assert pos["hedges"] == [{"date": "2026-10-02", "ts": "2026-10-02T10:15:00-04:00",
                              "shares": -50, "price": SPOT}]
    assert len(ledger.read_log("hedges")) == 1


def test_stop_cooloff_blocks_same_side_that_day(env, monkeypatch):
    data, spiked = snapshot(), snapshot()
    spiked["chain"]["mid"] = 15.0
    pick = lambda name, asof=None: (spiked if f"{asof:%H%M}" == "1115" else data)[name]
    monkeypatch.setattr(runner.store, "load", pick)
    ib = FakeIB()
    Fixed.vol = 0.10
    runner.run(ib, env, DAY1)
    runner.run(ib, env, at(1, "11:15"))
    assert ledger.read_log("trades")["reason"].iloc[-1] == "stop"
    assert ledger.load_position() is None
    runner.run(ib, env, at(1, "12:15"))
    assert ledger.load_position() is None
    runner.run(ib, env, DAY2)
    assert ledger.load_position()["side"] == "short"


@pytest.mark.parametrize("err", [RuntimeError("boom"), SystemExit("refused")])
def test_shadow_failure_never_blocks_publish(monkeypatch, capsys, err):
    from lsgamma.trading import shadow
    def fail():
        raise err
    monkeypatch.setattr(runner.desk, "write", lambda chain, cfg: "desk.json")
    monkeypatch.setattr(shadow, "write", fail)
    runner.publish(None, None)
    assert "shadow books not written" in capsys.readouterr().out


def book(env, monkeypatch):
    # put20 book on a chain with put skew
    from lsgamma.backtest import config as research
    cfg = research.variant("2026-11-02-lower-delta", "put20")
    cfg["signal"]["forecaster"] = "fixed"
    data = snapshot()
    c = data["chain"]
    data["chain"] = c.assign(delta=np.where(c["right"] == "C", 0.5, -(c["strike"] - 590) / 20), gamma=0.01)
    monkeypatch.setattr(runner.store, "load", lambda name, asof=None: data[name])
    return cfg, data


SKEW = {("P", 595.0): -0.25, ("P", 600.0): -0.5, ("P", 605.0): -0.75}


def test_book_enters_sized_otm_put(env, monkeypatch):
    cfg, data = book(env, monkeypatch)
    t, qty = runner.pick("short", data["chain"], cfg, DAY1)
    assert t["strike"] == 595.0 and qty > 1
    runner.run(FakeIB(deltas=SKEW), cfg, DAY1)
    pos = ledger.load_position()
    assert (pos["side"], pos["strike"], pos["qty"]) == ("short", 595.0, qty)
    assert pos["hedges"][0]["shares"] == -25 * qty


def test_paper_rules_still_atm_one_contract(env):
    t, qty = runner.pick("short", snapshot()["chain"], env, DAY1)
    assert t["strike"] == 600.0 and qty == 1


def test_partial_open_records_filled_qty(env):
    env["size"]["quantity"] = 9
    Fixed.vol = 0.10
    runner.run(FakeIB(partial={"OPT": 5}), env, DAY1)
    pos = ledger.load_position()
    assert pos["qty"] == 5 and pos["hedges"][0]["shares"] == -250
    assert ledger.read_log("trades")["qty"].tolist() == [5]


def test_partial_close_keeps_rest_open(env):
    env["size"]["quantity"] = 9
    ib = FakeIB()
    Fixed.vol = 0.10
    runner.run(ib, env, DAY1)
    Fixed.vol = 0.25
    ib.partial = {"OPT": 4}
    runner.run(ib, env, DAY2)
    pos = ledger.load_position()
    assert (pos["side"], pos["qty"]) == ("short", 5)
    t = ledger.read_log("trades")
    assert t["action"].tolist() == ["open", "close"] and t["qty"].tolist() == [9, 4]
    runner.run(ib, env, at(5))
    t = ledger.read_log("trades")
    assert t["action"].tolist() == ["open", "close", "close", "open"]
    assert t["qty"].tolist() == [9, 4, 5, 9] and ledger.load_position()["side"] == "long"


def test_nothing_filled_changes_nothing(env):
    Fixed.vol = 0.10
    ib = FakeIB(partial={"OPT": 0})
    runner.run(ib, env, DAY1)
    assert ledger.load_position() is None and ledger.read_log("trades").empty
    assert [o[0] for o in ib.orders] == ["OPT"]


def test_partial_hedge_logs_filled_shares(env):
    Fixed.vol = 0.10
    runner.run(FakeIB(partial={"STK": 20}), env, DAY1)
    assert ledger.read_log("hedges")["shares"].tolist() == [-20]
    assert ledger.load_position()["hedges"][0]["shares"] == -20


def test_reconcile_compares_contracts(env, capsys):
    ib = FakeIB()
    Fixed.vol = 0.10
    runner.run(ib, env, DAY1)
    pos = ledger.load_position()
    capsys.readouterr()
    runner.reconcile(ib, pos)
    assert "WARNING" not in capsys.readouterr().out
    runner.reconcile(ib, {**pos, "qty": 2})
    assert "WARNING: IBKR holds" in capsys.readouterr().out


@pytest.mark.parametrize("flag, value", [("ww_band", 30.0), ("size_tilt", 0.5), ("put_picks", "x.parquet"),
                                         ("crash_dte", [1, 10, 20]), ("fit_years", 3), ("max_positions", 2),
                                         ("long_hedge_band", 30)])
def test_check_book_refuses_research_flags(flag, value):
    from lsgamma.backtest import config as research
    cfg = research.variant("2026-11-02-lower-delta", "put20")
    runner.check_book(cfg)
    runner.check_book(config.read())
    runner.check_book({**cfg, "backtest": {**cfg["backtest"], "spread_mult": 2.0}})
    with pytest.raises(SystemExit, match=flag):
        runner.check_book({**cfg, "backtest": {**cfg["backtest"], flag: value}})


def test_shadow_books_are_tradable_except_hourly():
    from lsgamma.backtest import config as research
    from lsgamma.trading import shadow
    for b in research.read(shadow.PATH)["book"]:
        cfg = shadow.book_cfg(b, 250000)
        if b.get("placeholder"):
            with pytest.raises(SystemExit):
                runner.check_schedule(cfg)
        else:
            runner.check_schedule(cfg)
            runner.check_book(cfg)


def test_switch_dry_run_flips_into_the_book(env, monkeypatch, capsys):
    Fixed.vol = 0.25
    runner.run(FakeIB(), env, DAY1)
    assert ledger.load_position()["side"] == "long"
    cfg, data = book(env, monkeypatch)
    capsys.readouterr()
    runner.run(None, cfg, DAY2, dry=True)
    out = capsys.readouterr().out
    _, qty = runner.pick("short", data["chain"], cfg, DAY2)
    assert "exit flip" in out and "would close (flip)" in out
    assert f"enter short: short_put P 595.0 2026-10-30 x{qty}" in out


def test_main_refuses_unsupported_book_before_connecting(monkeypatch):
    from lsgamma.backtest import config as research
    cfg = research.variant("2026-11-02-lower-delta", "put20")
    cfg["backtest"]["ww_band"] = 30.0
    monkeypatch.setattr(runner.config, "load", lambda path=None: cfg)
    monkeypatch.setattr(runner.broker, "connect", lambda **k: pytest.fail("connected"))
    monkeypatch.setattr("sys.argv", ["runner", "--skip-pipeline"])
    with pytest.raises(SystemExit, match="ww_band"):
        runner.main()
