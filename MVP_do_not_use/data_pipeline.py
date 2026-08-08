"""
Data pipeline for volatility forecasting.

Sources:
    yfinance  -> SPY daily OHLC + intraday bars (returns, realized variance)
    CBOE      -> VIX history (direct CSV download, no API key)
    WRDS      -> optional CRSP daily returns (only used if --wrds flag passed
                 and the `wrds` package + credentials are available)

Outputs (into --outdir, default ./data):
    returns.csv   col 'ret'  -> input for garch_forecast.py
    rv.csv        col 'rv'   -> input for har_forecast.py (daily realized VARIANCE)
    vix.csv       cols 'date','vix'  -> for VRP/regime analysis (not used by forecasts)

Realized variance methods (--rv-method):
    intraday  5-min bars summed intraday (best, but yfinance only serves ~60 days)
    gk        Garman-Klass from daily OHLC (good proxy, long history)  [default]
    cc        squared close-to-close returns (crudest)

Usage:
    python data_pipeline.py                       # SPY, 5y, GK realized variance
    python data_pipeline.py --years 10 --rv-method cc
    python data_pipeline.py --wrds                # pull returns from CRSP instead
"""

import argparse
import io
import os

import numpy as np
import pandas as pd
import requests
import yfinance as yf

VIX_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"


# ---------------- yfinance ----------------
def fetch_daily(symbol: str, years: int) -> pd.DataFrame:
    df = yf.download(symbol, period=f"{years}y", interval="1d",
                     auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):          # newer yfinance versions
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


def log_returns(df: pd.DataFrame) -> pd.Series:
    return np.log(df["Close"]).diff().dropna().rename("ret")


# ---------------- realized variance ----------------
def rv_gk(df: pd.DataFrame) -> pd.Series:
    """Garman-Klass daily realized variance from OHLC."""
    hl = np.log(df["High"] / df["Low"]) ** 2
    co = np.log(df["Close"] / df["Open"]) ** 2
    return (0.5 * hl - (2 * np.log(2) - 1) * co).dropna().rename("rv")


def rv_cc(df: pd.DataFrame) -> pd.Series:
    """Squared close-to-close log returns."""
    return (log_returns(df) ** 2).rename("rv")


def rv_intraday(symbol: str) -> pd.Series:
    """Sum of squared 5-min log returns per day (~60 days max from yfinance)."""
    df = yf.download(symbol, period="60d", interval="5m",
                     auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    r = np.log(df["Close"]).diff().dropna()
    return (r ** 2).groupby(r.index.date).sum().rename("rv")


# ---------------- CBOE ----------------
def fetch_vix() -> pd.DataFrame:
    resp = requests.get(VIX_URL, timeout=30)
    resp.raise_for_status()
    vix = pd.read_csv(io.StringIO(resp.text))
    vix.columns = [c.strip().lower() for c in vix.columns]
    vix = vix.rename(columns={"close": "vix"})[["date", "vix"]]
    vix["date"] = pd.to_datetime(vix["date"])
    return vix.dropna()


# ---------------- WRDS (optional) ----------------
def fetch_crsp_returns(years: int, permno: int = 84398) -> pd.Series:
    """CRSP daily returns via WRDS. Default permno 84398 = SPY.
    Requires `pip install wrds` and a configured .pgpass / credentials."""
    import wrds
    db = wrds.Connection()
    q = f"""
        select date, ret from crsp.dsf
        where permno = {permno}
          and date >= current_date - interval '{years} years'
        order by date
    """
    df = db.raw_sql(q, date_cols=["date"])
    db.close()
    # CRSP gives simple returns; convert to log
    return np.log1p(df.set_index("date")["ret"].dropna()).rename("ret")


# ---------------- main ----------------
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", default="SPY")
    p.add_argument("--years", type=int, default=5)
    p.add_argument("--rv-method", choices=["gk", "cc", "intraday"], default="gk")
    p.add_argument("--outdir", default="data")
    p.add_argument("--wrds", action="store_true", help="pull returns from CRSP instead of yfinance")
    p.add_argument("--skip-vix", action="store_true")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # --- prices / returns ---
    daily = fetch_daily(args.symbol, args.years)
    if args.wrds:
        ret = fetch_crsp_returns(args.years)
    else:
        ret = log_returns(daily)
    ret.to_frame().to_csv(os.path.join(args.outdir, "returns.csv"), index=False)
    print(f"returns.csv  {len(ret)} rows  (source: {'CRSP' if args.wrds else 'yfinance'})")

    # --- realized variance ---
    if args.rv_method == "intraday":
        rv = rv_intraday(args.symbol)
    elif args.rv_method == "cc":
        rv = rv_cc(daily)
    else:
        rv = rv_gk(daily)
    rv.to_frame().to_csv(os.path.join(args.outdir, "rv.csv"), index=False)
    print(f"rv.csv       {len(rv)} rows  (method: {args.rv_method})")

    # --- VIX ---
    if not args.skip_vix:
        try:
            vix = fetch_vix()
            vix.to_csv(os.path.join(args.outdir, "vix.csv"), index=False)
            print(f"vix.csv      {len(vix)} rows  (source: CBOE)")
        except Exception as e:
            print(f"VIX download failed ({e}) — continuing without it")

    print("\nDone. Feed into forecasts:")
    print(f"  python garch_forecast.py {args.outdir}/returns.csv 10")
    print(f"  python har_forecast.py {args.outdir}/rv.csv")


if __name__ == "__main__":
    main()