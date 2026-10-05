"""Features calculated from the raw datasets. No network calls.

Every row at date t uses only data up to and including t.
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def log_returns(spy):
    return np.log(spy["close"]).diff().rename("ret")


def rv_gk(spy):
    """Garman-Klass daily realized variance from OHLC."""
    hl = np.log(spy["high"] / spy["low"]) ** 2
    co = np.log(spy["close"] / spy["open"]) ** 2
    return (0.5 * hl - (2 * np.log(2) - 1) * co).rename("rv_gk")


def har_lags(rv):
    """HAR inputs: daily, weekly and monthly average realized variance."""
    return pd.DataFrame({
        "rv_d": rv,
        "rv_w": rv.rolling(5).mean(),
        "rv_m": rv.rolling(22).mean(),
    })


def trend(spy):
    close = spy["close"]
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()
    return pd.DataFrame({
        "ma50": ma50,
        "ma200": ma200,
        "above_ma50": (close > ma50).where(ma50.notna()),
        "above_ma200": (close > ma200).where(ma200.notna()),
    })


def term_structure(idx):
    """Below 1 = upward sloping (calm). Above 1 = inverted (stress)."""
    return pd.DataFrame({
        "vix9d_vix": idx["vix9d"] / idx["vix"],
        "vix_vix3m": idx["vix"] / idx["vix3m"],
    })


def vix_percentile(vix, window=TRADING_DAYS):
    """Where today's VIX sits within the past year, 0 to 1."""
    return vix.rolling(window).rank(pct=True).rename("vix_pct_1y")


def build_features(spy, idx):
    rv = rv_gk(spy)
    idx = idx.reindex(spy.index).ffill()
    return pd.concat([
        log_returns(spy),
        har_lags(rv),
        trend(spy),
        idx[["vix", "vix9d", "vix3m", "vvix"]],
        term_structure(idx),
        vix_percentile(idx["vix"]),
        (idx["irx"] / 100).rename("rf"),
    ], axis=1)


def atm_iv(chain):
    """Average call/put IV at the strike nearest spot, per expiry.

    NaN when that strike has no IV; never falls back to a farther strike.
    """
    rows = []
    for (expiry, dte), g in chain.groupby(["expiry", "dte"]):
        spot = g["und_price"].median()
        strike = g.loc[(g["strike"] - spot).abs().idxmin(), "strike"]
        rows.append({"expiry": expiry, "dte": dte, "strike": strike,
                     "atm_iv": g.loc[g["strike"] == strike, "iv"].mean()})
    return pd.DataFrame(rows, columns=["expiry", "dte", "strike", "atm_iv"])
