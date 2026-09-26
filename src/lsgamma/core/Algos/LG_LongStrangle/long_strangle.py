"""Long strangle: buy an OTM put and an OTM call."""

from lsgamma.core.Algos.broker import Leg, flip, submit


def legs(expiry, put_strike, call_strike):
    return [
        Leg("BUY", "P", put_strike, expiry),
        Leg("BUY", "C", call_strike, expiry),
    ]


def open_position(ib, expiry, put_strike, call_strike, quantity, slippage=0.0):
    return submit(ib, legs(expiry, put_strike, call_strike), quantity, slippage)


def close_position(ib, expiry, put_strike, call_strike, quantity, slippage=0.0):
    return submit(ib, flip(legs(expiry, put_strike, call_strike)), quantity, slippage)
