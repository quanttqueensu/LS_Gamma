from lsgamma.core.Algos.broker import MULTIPLIER

SIGN = {"long": 1, "short": -1}


def option_pnl(position, option_mark):
    move = option_mark - position["entry_price"]
    return SIGN[position["side"]] * move * MULTIPLIER * position["qty"]


def hedge_pnl(position, spot):
    hedges = position["hedges"]
    cost = sum(h["shares"] * h["price"] for h in hedges)
    return -cost + sum(h["shares"] for h in hedges) * spot


def combined_pnl(position, option_mark, spot):
    return option_pnl(position, option_mark) + hedge_pnl(position, spot)


def premium(position):
    return position["entry_price"] * MULTIPLIER * position["qty"]
