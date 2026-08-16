import pandas as pd

DATA = "Data/data"
TRAIN_END = "2021-12-31"

ev = pd.read_parquet(f"{DATA}/signals/realized_forward_EVALUATION_ONLY.parquet")
ev = ev[ev["target_dte"] == 28].copy()
ev["date"] = pd.to_datetime(ev["date"])

sig = pd.read_parquet(f"{DATA}/signals/regimes.parquet")
sig["date"] = pd.to_datetime(sig["date"])

j = sig[["date", "regime", "vrp", "iv_atm", "rv_forecast"]].merge(
    ev[["date", "rv_forward", "vrp_realized_atm"]], on="date").dropna()
train = j[j["date"] <= TRAIN_END]

print(f"{len(train)} training days\n")
print("realized VRP by regime (negative = realized beat implied)")
print(train.groupby("regime")["vrp_realized_atm"].agg(["count", "mean", "median"]).round(4))
print()
print("fraction of days where realized beat implied")
print(train.groupby("regime")["vrp_realized_atm"].apply(lambda s: (s < 0).mean()).round(3))
print()
print("forecast error by regime")
train = train.assign(err=train["rv_forecast"] - train["rv_forward"])
print(train.groupby("regime")["err"].agg(["mean", "std"]).round(4))