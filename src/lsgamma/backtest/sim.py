import math

from lsgamma.core.Algos.broker import MULTIPLIER, TICK
from lsgamma.trading.pnl import SIGN
from lsgamma.trading.selection import to_date

DEFAULT_SRC = "fill_smile"


def book():
    return {"open": [], "shares": 0, "cash": 0.0, "fees": 0.0}


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


def pay(b, amount, cost, pos=None):
    b["cash"] -= amount + cost
    b["fees"] += cost
    if pos is not None:
        pos["fees"] += cost
    return cost


def open_option(b, pos, cost):
    pos["mark"], pos["fees"] = pos["entry_price"], 0.0
    b["open"].append(pos)
    value = SIGN[pos["side"]] * pos["entry_price"] * MULTIPLIER * pos["qty"]
    return pay(b, value, cost, pos)


def close_option(b, pos, price, cost):
    value = SIGN[pos["side"]] * price * MULTIPLIER * pos["qty"]
    pay(b, -value, cost, pos)
    b["open"] = [p for p in b["open"] if p is not pos]
    return cost


def held(pos):
    return sum(h["shares"] for h in pos["hedges"])


def unallocated(b):
    # shares no open position owns
    left = b["shares"] - sum(held(p) for p in b["open"])
    return 0 if abs(left) < 1e-9 else left


def split(total, weights):
    if len(weights) == 1:
        return [total]
    w = [abs(x) for x in weights]
    return [total * x / sum(w) if sum(w) else total / len(w) for x in w]


def allot(gaps, shares):
    # each position takes its gap; rounding to largest
    if len(gaps) == 1:
        return [shares]
    parts = list(gaps)
    big = max(range(len(gaps)), key=lambda i: abs(gaps[i]))
    parts[big] += shares - sum(gaps)
    return parts


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


def equity(b, marks, spot):
    option = sum((SIGN[p["side"]] * m * MULTIPLIER * p["qty"] for p, m in zip(b["open"], marks)),
                 0.0)
    return {"cash": b["cash"], "option": option, "shares": b["shares"], "spot": spot,
            "fees": b["fees"], "equity": b["cash"] + option + b["shares"] * spot}
