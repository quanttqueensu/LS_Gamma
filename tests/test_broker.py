from datetime import date
from types import SimpleNamespace

from lsgamma.core.Algos import broker

EXPIRY = date(2026, 11, 6)


class FakeIB:
    def __init__(self):
        self.orders = []

    def qualifyContracts(self, *cs):
        for c in cs:
            c.conId = 1
        return cs

    def reqMktData(self, c, *a):
        return SimpleNamespace(contract=c, midpoint=lambda: 5.0, marketPrice=lambda: 5.0)

    def cancelMktData(self, c):
        pass

    def sleep(self, s):
        pass

    def placeOrder(self, contract, order):
        self.orders.append(order)
        return SimpleNamespace(contract=contract, order=order)


def test_stock_orders_are_day_orders():
    ib = FakeIB()
    broker.submit_stock(ib, -101)
    order = ib.orders[-1]
    assert (order.action, order.totalQuantity, order.tif) == ("SELL", 101, "DAY")


def test_option_orders_are_day_orders():
    ib = FakeIB()
    broker.submit(ib, [broker.Leg("BUY", "C", 775.0, EXPIRY)], 1, slippage=0.05)
    assert ib.orders[-1].tif == "DAY"
