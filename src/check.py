from pathlib import Path

import pandas as pd

import features as F

TRAIN_END = "2021-12-31"
JOIN_COLUMNS = ["regime", "spread_atm", "iv_atm", "rv_forecast"]
TARGET_COLUMNS = ["rv_forward", "vrp_realized_atm"]


def load(data_dir=F.DATA, tenor=F.PRIMARY_TENOR, train_end=TRAIN_END):
    sig = pd.read_parquet(Path(data_dir) / "signals" / "regimes.parquet")
    sig["date"] = F.to_dates(sig["date"])
    sig = sig.set_index("date")

    j = sig[JOIN_COLUMNS].join(
        F.targets(data_dir, tenor)[TARGET_COLUMNS], how="inner").dropna()
    j["error"] = j["rv_forecast"] - j["rv_forward"]
    return j[j.index <= train_end] if train_end else j


def by_regime(df):
    return {
        "realized_vrp": df.groupby("regime")["vrp_realized_atm"]
            .agg(["count", "mean", "median"]).round(4),
        "loss_rate": df.groupby("regime")["vrp_realized_atm"]
            .apply(lambda s: (s < 0).mean()).round(3),
        "forecast_error": df.groupby("regime")["error"]
            .agg(["mean", "std"]).round(4),
    }


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(F.DATA))
    ap.add_argument("--tenor", type=int, default=F.PRIMARY_TENOR)
    ap.add_argument("--train-end", default=TRAIN_END)
    a = ap.parse_args(argv)

    df = load(Path(a.data), a.tenor, a.train_end)
    tables = by_regime(df)

    print(f"{len(df)} days  {df.index.min().date()} to {df.index.max().date()}")
    print(f"base rate: premium positive {(df['vrp_realized_atm'] > 0).mean():.1%}\n")

    print("realized VRP by regime  (positive = implied exceeded realized)")
    print(tables["realized_vrp"].to_string())
    print("\nfraction of days where realized beat implied  (bad for short gamma)")
    print(tables["loss_rate"].to_string())
    print("\nforecast error by regime  (positive = over-forecast)")
    print(tables["forecast_error"].to_string())
    print("\nunconditional forecast error")
    print(f"  mean   {df['error'].mean():+.4f}")
    print(f"  median {df['error'].median():+.4f}")
    return df


if __name__ == "__main__":
    main()
