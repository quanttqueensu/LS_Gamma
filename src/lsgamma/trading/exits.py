from datetime import date

import numpy as np

from lsgamma.trading.pnl import premium

OPPOSITE = {"long": "short", "short": "long"}


def stopped(position, pnl, ex):
    frac = ex["short_stop_mult"] if position["side"] == "short" else ex["long_stop_frac"]
    return pnl <= -frac * premium(position)


def took_profit(position, pnl, ex):
    frac = ex["short_profit_frac"]
    return position["side"] == "short" and frac > 0 and pnl >= frac * premium(position)


def flat_run(history, n):
    return len(history) >= n and all(s == "flat" for s in history[-n:])


def exit_reason(position, today, pnl, signal, history, cfg):
    ex = cfg["exit"]
    if (date.fromisoformat(position["expiry"]) - today).days <= ex["exit_dte"]:
        return "time"
    if stopped(position, pnl, ex):
        return "stop"
    if took_profit(position, pnl, ex):
        return "profit"
    if signal == OPPOSITE[position["side"]]:
        return "flip"
    if flat_run(history, ex["flat_days"]):
        return "flat"
    return None


def cooling(side, last_stop, today, n):
    # last_stop: (side, date) of the latest stop
    if not n or last_stop is None or last_stop[0] != side:
        return False
    return bool(np.busday_count(str(last_stop[1]), str(today)) < n)
