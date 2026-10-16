from datetime import timedelta

import pandas as pd

TZ = "America/New_York"
SATURDAY = 5


def at(day, hhmm):
    return pd.Timestamp(f"{day} {hhmm}", tz=TZ)


def fridays(expiry):
    # pre-2015 monthlies list Saturday; last trade Friday
    sat = {e: e - timedelta(days=1) for e in expiry.unique() if e.weekday() == SATURDAY}
    return expiry.replace(sat) if sat else expiry


def window(trades, start, end, cfg):
    t = trades["ts"]
    keep = ((t > start) & (t <= end) & trades["conditions"].isin(cfg["conditions"])
            & (trades["price"] >= cfg["min_price"]))
    out = trades[keep]
    return out.assign(expiry=fridays(out["expiry"]))
