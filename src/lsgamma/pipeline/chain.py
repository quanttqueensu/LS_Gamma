"""SPY option chain snapshot from IBKR (delayed data is free on paper accounts)."""

import math
from datetime import date, datetime

import pandas as pd
from ib_async import Option, Stock

from lsgamma.core.Algos import broker

BATCH = 50  # stays under IBKR's 100 market data lines
WAIT = 5.0  # max seconds per batch for delayed quotes and greeks to arrive

COLUMNS = ["asof", "expiry", "dte", "strike", "right", "bid", "ask", "mid",
           "iv", "delta", "gamma", "vega", "theta", "und_price"]


def _price(x):
    return x if x is not None and not math.isnan(x) and x > 0 else math.nan


def _mid(ticker):
    try:
        return broker.mid(ticker)
    except ValueError:
        return math.nan


def _complete(t):
    return (not math.isnan(_price(t.bid)) and not math.isnan(_price(t.ask))
            and t.modelGreeks is not None and t.modelGreeks.delta is not None)


def _stream(ib, contracts, wait=WAIT):
    """Stream quotes until every ticker has bid/ask and greeks, or `wait` runs out.

    A reqTickers snapshot returns before most delayed quotes arrive, so we
    stream briefly instead and then cancel.
    """
    tickers = [ib.reqMktData(c, "", False, False) for c in contracts]
    waited = 0.0
    while waited < wait and not all(_complete(t) for t in tickers):
        ib.sleep(0.5)
        waited += 0.5
    for c in contracts:
        ib.cancelMktData(c)
    return tickers


def spot(ib, underlying=broker.UNDERLYING):
    stock = Stock(underlying, broker.EXCHANGE, broker.CURRENCY)
    ib.qualifyContracts(stock)
    return stock, _mid(ib.reqTickers(stock)[0])


def contracts(ib, stock, spot_price, min_dte, max_dte, strike_pct, fridays_only):
    params = ib.reqSecDefOptParams(stock.symbol, "", stock.secType, stock.conId)
    chain = next(c for c in params
                 if c.exchange == broker.EXCHANGE and c.tradingClass == stock.symbol)

    today = date.today()
    expiries = []
    for e in chain.expirations:
        d = datetime.strptime(e, "%Y%m%d").date()
        if min_dte <= (d - today).days <= max_dte and (not fridays_only or d.weekday() == 4):
            expiries.append(e)

    lo, hi = spot_price * (1 - strike_pct), spot_price * (1 + strike_pct)
    strikes = [k for k in chain.strikes if lo <= k <= hi]

    options = [
        Option(stock.symbol, e, k, right, broker.EXCHANGE,
               multiplier=str(broker.MULTIPLIER), currency=broker.CURRENCY,
               tradingClass=stock.symbol)
        for e in expiries for k in strikes for right in ("C", "P")
    ]
    # Not every strike is listed for every expiry. Unlisted ones stay unqualified.
    ib.qualifyContracts(*options)
    return [o for o in options if o.conId]


def option_chain(ib, min_dte=1, max_dte=60, strike_pct=0.10, fridays_only=True):
    stock, spot_price = spot(ib)
    if math.isnan(spot_price):
        raise RuntimeError("no SPY price from IBKR")

    opts = contracts(ib, stock, spot_price, min_dte, max_dte, strike_pct, fridays_only)
    asof = pd.Timestamp.now(tz="America/New_York")
    today = date.today()

    rows = []
    for i in range(0, len(opts), BATCH):
        for t in _stream(ib, opts[i:i + BATCH]):
            c, g = t.contract, t.modelGreeks
            expiry = datetime.strptime(c.lastTradeDateOrContractMonth, "%Y%m%d").date()
            rows.append({
                "asof": asof,
                "expiry": expiry,
                "dte": (expiry - today).days,
                "strike": c.strike,
                "right": c.right,
                "bid": _price(t.bid),
                "ask": _price(t.ask),
                "mid": _mid(t),
                "iv": g.impliedVol if g else None,
                "delta": g.delta if g else None,
                "gamma": g.gamma if g else None,
                "vega": g.vega if g else None,
                "theta": g.theta if g else None,
                "und_price": g.undPrice if g else spot_price,
            })

    df = pd.DataFrame(rows, columns=COLUMNS)
    return df.sort_values(["expiry", "strike", "right"]).reset_index(drop=True)
