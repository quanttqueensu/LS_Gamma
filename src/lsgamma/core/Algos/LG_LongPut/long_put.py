"""Long put: buy one put. Long gamma, long vega, pays theta."""

from lsgamma.core.Algos.broker import Leg, flip, submit


def legs(expiry, strike):
    return [
        Leg("BUY", "P", strike, expiry),
    ]


def open_position(ib, expiry, strike, quantity, slippage=0.0):
    return submit(ib, legs(expiry, strike), quantity, slippage)


def close_position(ib, expiry, strike, quantity, slippage=0.0):
    return submit(ib, flip(legs(expiry, strike)), quantity, slippage)
