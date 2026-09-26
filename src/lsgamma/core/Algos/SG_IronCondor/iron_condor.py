"""Iron condor: short strangle plus long wings further OTM. Defined max loss.

Strikes must satisfy long_put < short_put < short_call < long_call.
"""

from lsgamma.core.Algos.broker import Leg, flip, submit


def legs(expiry, long_put, short_put, short_call, long_call):
    return [
        Leg("BUY", "P", long_put, expiry),
        Leg("SELL", "P", short_put, expiry),
        Leg("SELL", "C", short_call, expiry),
        Leg("BUY", "C", long_call, expiry),
    ]


def open_position(ib, expiry, long_put, short_put, short_call, long_call, quantity, slippage=0.0):
    return submit(ib, legs(expiry, long_put, short_put, short_call, long_call), quantity, slippage)


def close_position(ib, expiry, long_put, short_put, short_call, long_call, quantity, slippage=0.0):
    return submit(ib, flip(legs(expiry, long_put, short_put, short_call, long_call)), quantity, slippage)
