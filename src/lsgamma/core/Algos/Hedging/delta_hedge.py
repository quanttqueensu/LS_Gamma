"""Delta hedge: hold enough shares to make the book's Black-Scholes delta zero.

This is the benchmark every other hedger (e.g. deep hedging) is compared against.
"""

from lsgamma.core.Algos.broker import UNDERLYING
from lsgamma.core.Algos.Hedging.portfolio import option_delta, rebalance


def target_shares(ib, underlying=UNDERLYING):
    return -option_delta(ib, underlying)


def hedge(ib, ref, underlying=UNDERLYING, min_shares=1, pad=0.0):
    return rebalance(ib, target_shares(ib, underlying), ref, underlying, min_shares, pad)
