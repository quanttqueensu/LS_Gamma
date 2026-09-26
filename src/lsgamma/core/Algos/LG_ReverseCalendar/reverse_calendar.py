"""Reverse calendar: buy the near expiry, sell the far expiry, same strike.

Long gamma with reduced or negative vega. `right` is "C" or "P".
"""

from lsgamma.core.Algos.broker import Leg, flip, submit


def legs(near_expiry, far_expiry, strike, right):
    return [
        Leg("BUY", right, strike, near_expiry),
        Leg("SELL", right, strike, far_expiry),
    ]


def open_position(ib, near_expiry, far_expiry, strike, right, quantity, slippage=0.0):
    return submit(ib, legs(near_expiry, far_expiry, strike, right), quantity, slippage)


def close_position(ib, near_expiry, far_expiry, strike, right, quantity, slippage=0.0):
    return submit(ib, flip(legs(near_expiry, far_expiry, strike, right)), quantity, slippage)
