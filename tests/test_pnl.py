from lsgamma.trading import pnl

POS = {"side": "short", "right": "P", "expiry": "2026-10-30", "strike": 500.0, "qty": 1,
       "entry_price": 5.0, "entry_date": "2026-10-01",
       "hedges": [{"shares": 50, "price": 100.0, "date": "2026-10-01"},
                  {"shares": -20, "price": 102.0, "date": "2026-10-02"}]}


def test_option_pnl_short_put():
    assert pnl.option_pnl(POS, 4.0) == 100.0


def test_option_pnl_long():
    assert pnl.option_pnl({**POS, "side": "long", "qty": 2}, 4.0) == -200.0


def test_hedge_pnl():
    assert pnl.hedge_pnl(POS, 101.0) == 70.0


def test_combined_pnl():
    assert pnl.combined_pnl(POS, 4.0, 101.0) == 170.0


def test_premium():
    assert pnl.premium({**POS, "qty": 3}) == 1500.0
