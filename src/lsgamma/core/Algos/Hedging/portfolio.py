"""Shared helpers for every hedger: read the current book and rebalance shares.

A hedger only decides a target share position. rebalance() trades the
difference through the broker.
"""

from lsgamma.core.Algos.broker import EXCHANGE, MULTIPLIER, UNDERLYING, submit_stock


def stock_position(ib, underlying=UNDERLYING):
    return sum(p.position for p in ib.positions()
               if p.contract.symbol == underlying and p.contract.secType == "STK")


def option_positions(ib, underlying=UNDERLYING):
    positions = []
    for p in ib.positions():
        c = p.contract
        if c.symbol == underlying and c.secType == "OPT":
            c.exchange = EXCHANGE
            positions.append((c, p.position))
    return positions


def option_delta(ib, underlying=UNDERLYING):
    """Delta of the option positions only, in shares."""
    positions = option_positions(ib, underlying)
    if not positions:
        return 0.0

    tickers = ib.reqTickers(*[c for c, _ in positions])
    delta = 0.0
    for (c, qty), t in zip(positions, tickers):
        if t.modelGreeks is None or t.modelGreeks.delta is None:
            raise ValueError(f"no delta for {c.localSymbol}")
        delta += t.modelGreeks.delta * qty * MULTIPLIER
    return delta


def rebalance(ib, target_shares, underlying=UNDERLYING, min_shares=1):
    """Trade shares so the stock position equals target_shares. Returns None if no trade needed."""
    shares = round(target_shares - stock_position(ib, underlying))
    if abs(shares) < min_shares:
        return None
    return submit_stock(ib, shares, underlying)
