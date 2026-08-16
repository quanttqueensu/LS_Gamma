from pathlib import Path

import pandas as pd

from Classification import classify_frame
from Forecast_Models.garch import forecast_series, load_returns

DATA = Path(__file__).resolve().parent / "Data" / "data"
TENOR = 28
HORIZON = round(TENOR * 252 / 365)
START = "2024-01-01"

dates, returns = load_returns(DATA / "reference" / "spy_daily.parquet")
rv = forecast_series(dates, returns, HORIZON)
rv.index = pd.to_datetime(rv.index)

df = pd.read_parquet(DATA / "signals" / "daily_signal.parquet")
df = df[df["target_dte"] == TENOR].copy()
df["date"] = pd.to_datetime(df["date"])
df["rv_forecast"] = df["date"].map(rv)


out = classify_frame(df)
out.to_parquet(DATA / "signals" / "regimes.parquet", index=False)

recent = out[out["date"] >= START]
print(f"{START} to {recent['date'].max().date()}  ({len(recent)} days)")
print(recent["regime"].value_counts())
print(recent[["date", "iv_atm", "rv_forecast", "vrp", "regime"]].tail(15).to_string(index=False))