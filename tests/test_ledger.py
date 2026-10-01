from datetime import date

import pytest

from lsgamma.trading import config, ledger


@pytest.fixture(autouse=True)
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setattr(ledger, "ROOT", tmp_path / "paper")


def test_position_round_trip():
    pos = {"algo": "LG_straddle", "opened": date(2026, 10, 1),
           "hedges": [{"shares": 10, "price": 570.5}, {"shares": -5, "price": 572.0}]}
    ledger.save_position(pos)
    got = ledger.load_position()
    assert got["opened"] == "2026-10-01"
    assert got["hedges"] == pos["hedges"]
    assert got["algo"] == "LG_straddle"


def test_load_missing_is_none():
    assert ledger.load_position() is None


def test_clear():
    ledger.save_position({"algo": "x"})
    ledger.clear_position()
    assert ledger.load_position() is None
    ledger.clear_position()


def test_log_appends():
    for i in range(3):
        ledger.log("fills", {"i": i, "price": 1.0 + i})
    df = ledger.read_log("fills")
    assert len(df) == 3
    assert df["i"].tolist() == [0, 1, 2]


def test_read_log_missing_is_empty():
    assert ledger.read_log("nothing").empty


def test_signal_history():
    for s in ["long", "flat", "short"]:
        ledger.log("signals", {"signal": s})
    assert ledger.signal_history(2) == ["flat", "short"]


def test_config_bands():
    cfg = config.load()
    assert cfg["signal"]["long_band"] == 0.05
    assert cfg["signal"]["short_band"] == -0.02
