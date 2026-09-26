"""Long straddle: buy a call and a put at the same strike."""

from lsgamma.core.Algos.broker import Leg, flip, submit


def legs(expiry, strike):
    return [
        Leg("BUY", "C", strike, expiry),
        Leg("BUY", "P", strike, expiry),
    ]


def open_position(ib, expiry, strike, quantity, slippage=0.0):
    return submit(ib, legs(expiry, strike), quantity, slippage)


def close_position(ib, expiry, strike, quantity, slippage=0.0):
    return submit(ib, flip(legs(expiry, strike)), quantity, slippage)
