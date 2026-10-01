from datetime import date

from lsgamma.core.Algos.LG_LongCall import long_call
from lsgamma.core.Algos.SG_ShortPut import short_put

RIGHTS = {"long": "C", "short": "P"}
ALGOS = {"long": long_call, "short": short_put}
FRIDAY = 4


def to_date(expiry):
    return date.fromisoformat(expiry) if isinstance(expiry, str) else expiry


def pick_expiry(chain, cfg):
    entry = cfg["entry"]
    pairs = chain[["expiry", "dte"]].drop_duplicates()
    pairs = pairs[pairs["expiry"].map(lambda e: e.weekday() == FRIDAY)]
    pairs = pairs[pairs["dte"].between(entry["min_dte"], entry["max_dte"])]
    if pairs.empty:
        raise ValueError("no Friday expiry in the dte window")
    pairs = pairs.assign(gap=(pairs["dte"] - entry["target_dte"]).abs())
    return pairs.sort_values(["gap", "dte"]).iloc[0]["expiry"]


def pick_strike(chain, expiry, right):
    rows = chain[(chain["expiry"] == to_date(expiry)) & (chain["right"] == right)]
    rows = rows.dropna(subset=["mid"])
    spot = rows["und_price"].median()
    return float(rows.loc[(rows["strike"] - spot).abs().idxmin(), "strike"])


def mark(chain, expiry, strike, right):
    rows = chain[(chain["expiry"] == to_date(expiry)) & (chain["strike"] == strike)
                 & (chain["right"] == right)]
    return float("nan") if rows.empty else float(rows["mid"].iloc[0])


def trade_for(side, chain, cfg):
    right = RIGHTS[side]
    expiry = pick_expiry(chain, cfg)
    return {"side": side, "algo": ALGOS[side], "right": right, "expiry": expiry,
            "strike": pick_strike(chain, expiry, right)}
