"""Short call: sell one call. Short gamma, short vega, collects theta."""

from lsgamma.core.Algos.broker import Leg, flip, submit


def legs(expiry, strike):
    return [
        Leg("SELL", "C", strike, expiry),
    ]


def open_position(ib, expiry, strike, quantity, slippage=0.0):
    return submit(ib, legs(expiry, strike), quantity, slippage)


def close_position(ib, expiry, strike, quantity, slippage=0.0):
    return submit(ib, flip(legs(expiry, strike)), quantity, slippage)
