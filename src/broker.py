from contextlib import contextmanager

from ib_async import IB, LimitOrder, Option

HOST = "127.0.0.1"
PORT_PAPER_TWS = 7497
PORT_LIVE_TWS = 7496
PORT_PAPER_GATEWAY = 4002
PORT_LIVE_GATEWAY = 4001

CLIENT_ID = 1
EXCHANGE = "SMART"
CURRENCY = "USD"
MULTIPLIER = "100"
PAPER_ACCOUNT_PREFIX = "DU"


class LiveTradingBlocked(RuntimeError):
    pass


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
        yield ib
    finally:
        ib.disconnect()


def to_contract(underlying, expiry, right, strike):
    return Option(
        underlying,
        expiry.strftime("%Y%m%d"),
        float(strike),
        right,
        EXCHANGE,
        multiplier=MULTIPLIER,
        currency=CURRENCY,
    )


def qualify(ib, position):
    contracts = [
        to_contract(position["underlying"], position["expiry"], leg["right"], leg["strike"])
        for leg in position["legs"]
    ]
    qualified = ib.qualifyContracts(*contracts)
    if len(qualified) != len(contracts):
        raise ValueError("could not qualify all legs")
    return qualified


def place(ib, position, limit_slippage=0.0, wait=2):
    contracts = qualify(ib, position)
    trades = []

    for contract, leg in zip(contracts, position["legs"]):
        if leg["quantity"] <= 0:
            continue
        pad = limit_slippage if leg["side"] == "BUY" else -limit_slippage
        price = round(leg["price"] + pad, 2)
        order = LimitOrder(leg["side"], leg["quantity"], price, tif="DAY")
        trades.append(ib.placeOrder(contract, order))

    ib.sleep(wait)
    return trades


def status(trades):
    return [
        {
            "symbol": t.contract.localSymbol,
            "side": t.order.action,
            "quantity": t.order.totalQuantity,
            "limit_price": t.order.lmtPrice,
            "status": t.orderStatus.status,
            "filled": t.orderStatus.filled,
            "avg_fill": t.orderStatus.avgFillPrice,
        }
        for t in trades
    ]


def open_positions(ib):
    return [
        {
            "symbol": p.contract.localSymbol,
            "quantity": p.position,
            "avg_cost": p.avgCost,
        }
        for p in ib.positions()
    ]


def net_liquidation(ib):
    for row in ib.accountSummary():
        if row.tag == "NetLiquidation":
            return float(row.value)
    return float("nan")