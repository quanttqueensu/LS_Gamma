"""Daily SPY prices and volatility indices from yfinance (free)."""

import pandas as pd
import yfinance as yf

INDICES = {
    "^VIX": "vix",
    "^VIX9D": "vix9d",
    "^VIX3M": "vix3m",
    "^VVIX": "vvix",
    "^IRX": "irx",
}


def _download(tickers, years):
    df = yf.download(tickers, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False)
    if df.empty:
        raise RuntimeError(f"yfinance returned no data for {tickers}")
    return df


def spy_daily(years=5, symbol="SPY"):
    df = _download(symbol, years)
    if isinstance(df.columns, pd.MultiIndex):  # newer yfinance versions
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df.columns = ["open", "high", "low", "close", "volume"]
    df.index = pd.to_datetime(df.index).tz_localize(None).rename("date")
    return df


def indices(years=5):
    df = _download(list(INDICES), years)["Close"]
    df = df.rename(columns=INDICES)[list(INDICES.values())]
    df.columns.name = None
    df.index = pd.to_datetime(df.index).tz_localize(None).rename("date")
    return df.dropna(how="all")
