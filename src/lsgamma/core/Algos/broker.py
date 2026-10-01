"""Shared IBKR execution layer used by every algo in this folder.

Algos only describe their legs. This module connects to TWS/Gateway,
prices the legs, and sends them as a single order (a combo order when
there is more than one leg, so every leg fills together or not at all).
Hedgers in Hedging/ decide share targets and send them via submit_stock().
"""

import math
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import date

from ib_async import IB, Bag, ComboLeg, LimitOrder, MarketOrder, Option, Stock

HOST = "127.0.0.1"
PORT_PAPER_TWS = 7497
PORT_LIVE_TWS = 7496
PORT_PAPER_GATEWAY = 4002
PORT_LIVE_GATEWAY = 4001

CLIENT_ID = 1
UNDERLYING = "SPY"
EXCHANGE = "SMART"
CURRENCY = "USD"
MULTIPLIER = 100
PAPER_ACCOUNT_PREFIX = "DU"
TICK = 0.01

# 3 = delay
MARKET_DATA_TYPE = 3


class LiveTradingBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Leg:
    action: str  # "BUY" or "SELL"
    right: str  # "C" or "P"
    strike: float
    expiry: date
    ratio: int = 1


def flip(legs):
    return [replace(leg, action="SELL" if leg.action == "BUY" else "BUY") for leg in legs]


#connection

def port_for(paper=True, gateway=False):
    if gateway:
        return PORT_PAPER_GATEWAY if paper else PORT_LIVE_GATEWAY
    return PORT_PAPER_TWS if paper else PORT_LIVE_TWS


def verify_paper(ib):
    accounts = ib.managedAccounts()
    if not accounts:
        raise LiveTradingBlocked("no account returned by TWS")
    live = [a for a in accounts if not a.startswith(PAPER_ACCOUNT_PREFIX)]
    if live:
        raise LiveTradingBlocked(f"live account connected: {live}")
    return accounts


@contextmanager
def connect(paper=True, gateway=False, client_id=CLIENT_ID, host=HOST):
    ib = IB()
    ib.connect(host, port_for(paper, gateway), clientId=client_id)
    try:
        if paper:
            verify_paper(ib)
        ib.reqMarketDataType(MARKET_DATA_TYPE)
        yield ib
    finally:
        ib.disconnect()


# contract + Pricing

def to_contract(leg, underlying=UNDERLYING):
    return Option(
        underlying,
        leg.expiry.strftime("%Y%m%d"),
        float(leg.strike),
        leg.right,
        EXCHANGE,
        multiplier=str(MULTIPLIER),
        currency=CURRENCY,
    )


def qualify(ib, legs, underlying=UNDERLYING):
    contracts = [to_contract(leg, underlying) for leg in legs]
    ib.qualifyContracts(*contracts)
    missing = [leg for leg, c in zip(legs, contracts) if not c.conId]
    if missing:
        raise ValueError(f"could not qualify legs: {missing}")
    return contracts


def mid(ticker):
    price = ticker.midpoint()
    if math.isnan(price):
        price = ticker.marketPrice()
    if math.isnan(price):
        raise ValueError(f"no price for {ticker.contract.localSymbol}")
    return price


def stream(ib, contracts, ready, wait=5.0):
    # delayed snapshots arrive empty, so stream briefly
    tickers = [ib.reqMktData(c, "", False, False) for c in contracts]
    waited = 0.0
    while waited < wait and not all(ready(t) for t in tickers):
        ib.sleep(0.5)
        waited += 0.5
    for c in contracts:
        ib.cancelMktData(c)
    return tickers


def has_mid(ticker):
    return not math.isnan(ticker.midpoint())


def net_mid(ib, legs, contracts):
    tickers = stream(ib, contracts, has_mid)
    sign = {"BUY": 1, "SELL": -1}
    return sum(sign[leg.action] * leg.ratio * mid(t) for leg, t in zip(legs, tickers))


def round_tick(price):
    return round(round(price / TICK) * TICK, 2)


#orders

def submit(ib, legs, quantity, slippage=0.0, underlying=UNDERLYING, tif="DAY"):
    
    if quantity <= 0:
        raise ValueError("quantity must be positive")

    contracts = qualify(ib, legs, underlying)
    net = net_mid(ib, legs, contracts)

    if len(legs) == 1:
        contract = contracts[0]
        action = legs[0].action
    else:
        action = "BUY" if net >= 0 else "SELL"
        combo_legs = legs if action == "BUY" else flip(legs)
        contract = Bag(
            symbol=underlying,
            exchange=EXCHANGE,
            currency=CURRENCY,
            comboLegs=[
                ComboLeg(conId=c.conId, ratio=leg.ratio, action=leg.action, exchange=EXCHANGE)
                for leg, c in zip(combo_legs, contracts)
            ],
        )

    pad = slippage if action == "BUY" else -slippage
    price = max(round_tick(abs(net) + pad), TICK)
    order = LimitOrder(action, quantity, price, tif=tif)
    return ib.placeOrder(contract, order)


def submit_stock(ib, shares, underlying=UNDERLYING):
    """Market order for `shares` of the underlying. Positive = buy, negative = sell."""
    if shares == 0:
        raise ValueError("shares must be non-zero")
    stock = Stock(underlying, EXCHANGE, CURRENCY)
    ib.qualifyContracts(stock)
    order = MarketOrder("BUY" if shares > 0 else "SELL", abs(shares))
    return ib.placeOrder(stock, order)


def wait_for_fill(ib, trade, timeout=30):
    waited = 0.0
    while not trade.isDone() and waited < timeout:
        ib.sleep(0.5)
        waited += 0.5
    return trade.orderStatus.status


def status(trade):
    return {
        "symbol": trade.contract.localSymbol or trade.contract.symbol,
        "side": trade.order.action,
        "quantity": trade.order.totalQuantity,
        "limit_price": trade.order.lmtPrice,
        "status": trade.orderStatus.status,
        "filled": trade.orderStatus.filled,
        "avg_fill": trade.orderStatus.avgFillPrice,
    }
