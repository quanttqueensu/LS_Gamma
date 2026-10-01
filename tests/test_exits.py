from datetime import date

from lsgamma.trading.exits import exit_reason

CFG = {"exit": {"exit_dte": 7, "flat_days": 3, "short_stop_mult": 1.0,
                "long_stop_frac": 0.5, "short_profit_frac": 0.5}}
TODAY = date(2026, 10, 1)
SHORT = {"side": "short", "right": "P", "expiry": "2026-10-30", "strike": 500.0, "qty": 1,
         "entry_price": 5.0, "entry_date": "2026-09-29", "hedges": []}
LONG = {**SHORT, "side": "long", "right": "C"}


def reason(pos, pnl=0.0, signal="short", history=None, today=TODAY, cfg=CFG):
    return exit_reason(pos, today, pnl, signal, history or [signal], cfg)


def test_nothing_fires():
    assert reason(SHORT) is None
    assert reason(LONG, signal="long") is None


def test_time():
    assert reason(SHORT, today=date(2026, 10, 23)) == "time"
    assert reason(SHORT, today=date(2026, 10, 22)) is None


def test_short_stop():
    assert reason(SHORT, pnl=-500.0) == "stop"
    assert reason(SHORT, pnl=-499.0) is None


def test_long_stop():
    assert reason(LONG, pnl=-250.0, signal="long") == "stop"
    assert reason(LONG, pnl=-249.0, signal="long") is None


def test_profit():
    assert reason(SHORT, pnl=250.0) == "profit"
    assert reason(SHORT, pnl=249.0) is None


def test_profit_disabled_and_long_has_none():
    cfg = {"exit": {**CFG["exit"], "short_profit_frac": 0}}
    assert reason(SHORT, pnl=1000.0, cfg=cfg) is None
    assert reason(LONG, pnl=1000.0, signal="long") is None


def test_flip():
    assert reason(SHORT, signal="long") == "flip"
    assert reason(LONG, signal="short") == "flip"


def test_flat():
    assert reason(SHORT, signal="flat", history=["flat", "flat", "flat"]) == "flat"
    assert reason(SHORT, signal="flat", history=["short", "flat", "flat"]) is None
    assert reason(SHORT, signal="flat", history=["flat", "flat"]) is None


def test_priority():
    late = date(2026, 10, 25)
    assert reason(SHORT, pnl=-1000.0, today=late) == "time"
    assert reason(SHORT, pnl=-1000.0, signal="long") == "stop"
    assert reason(SHORT, pnl=300.0, signal="long") == "profit"
    assert reason(SHORT, signal="long", history=["flat", "flat", "long"]) == "flip"
    assert reason(LONG, signal="short", history=["flat", "flat", "short"]) == "flip"
