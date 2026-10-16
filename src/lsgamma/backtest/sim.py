import math

from lsgamma.core.Algos.broker import MULTIPLIER, TICK
from lsgamma.trading.pnl import SIGN
from lsgamma.trading.selection import to_date

DEFAULT_SRC = "fill_smile"


def book():
    return {"pos": None, "shares": 0, "cash": 0.0, "fees": 0.0, "mark": math.nan, "pos_fees": 0.0}


def row(chain, expiry, strike, right):
    if chain is None:
        return None
    rows = chain[(chain["expiry"] == to_date(expiry)) & (chain["strike"] == strike)
                 & (chain["right"] == right)]
    return None if rows.empty else rows.iloc[0]


def buys(side, action):
    return (action == "open") == (side == "long")


def option_fill(fill, side, expiry, strike, right, action, mult):
    r = row(fill, expiry, strike, right)
    if r is None:
        return math.nan, None
    price = r["mid"] + (1 if buys(side, action) else -1) * (r["ask"] - r["bid"]) / 2 * mult
    src = r["src"] if "src" in r.index else DEFAULT_SRC
    return (math.nan if math.isnan(price) else max(float(price), TICK)), src


def und_price(fill):
    return math.nan if fill is None else float(fill["und_price"].median())


def share_price(fill, shares, half):
    return und_price(fill) + (half if shares > 0 else -half)


def target_shares(pos, chain):
    if pos is None:
        return 0.0
    r = row(chain, pos["expiry"], pos["strike"], pos["right"])
    delta = math.nan if r is None else float(r["delta"])
    return -delta * pos["qty"] * MULTIPLIER * SIGN[pos["side"]]


def fee(per, units, minimum):
    return max(per * units, minimum)


def pay(b, amount, cost):
    b["cash"] -= amount + cost
    b["fees"] += cost
    b["pos_fees"] += cost
    return cost


def open_option(b, pos, cost):
    b["pos"], b["mark"], b["pos_fees"] = pos, pos["entry_price"], 0.0
    value = SIGN[pos["side"]] * pos["entry_price"] * MULTIPLIER * pos["qty"]
    return pay(b, value, cost)


def close_option(b, price, cost):
    pos = b["pos"]
    value = SIGN[pos["side"]] * price * MULTIPLIER * pos["qty"]
    pay(b, -value, cost)
    b["pos"], b["mark"] = None, math.nan
    return cost


def trade_shares(b, shares, price, cost):
    b["shares"] += shares
    return pay(b, shares * price, cost)


def intrinsic(pos, spot):
    gap = spot - pos["strike"] if pos["right"] == "C" else pos["strike"] - spot
    return max(gap, 0.0)


def conservative(pos, last, spot):
    # unmarked: short worth more, long less
    floor = intrinsic(pos, spot)
    if math.isnan(last):
        return floor
    return max(last, floor) if pos["side"] == "short" else min(last, floor)


def equity(b, mark, spot):
    pos = b["pos"]
    option = 0.0 if pos is None else SIGN[pos["side"]] * mark * MULTIPLIER * pos["qty"]
    return {"cash": b["cash"], "option": option, "shares": b["shares"], "spot": spot,
            "fees": b["fees"], "equity": b["cash"] + option + b["shares"] * spot}
