from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("Data/data")
TENOR = 28
TRAIN_END = "2021-12-31"


def build():
    ev = pd.read_parquet(DATA / "signals" / "realized_forward_EVALUATION_ONLY.parquet")
    ev = ev[ev["target_dte"] == TENOR].copy()
    ev["date"] = pd.to_datetime(ev["date"])

    ts = pd.read_parquet(DATA / "surface" / "term_structure.parquet")
    ts["date"] = pd.to_datetime(ts["date"])
    wide = ts.pivot_table(index="date", columns="target_dte", values="atm_iv")
    main = ts[ts["target_dte"] == TENOR].set_index("date")

    spy = pd.read_parquet(DATA / "reference" / "spy_daily.parquet")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.set_index("date")
    r = np.log1p(spy["ret_ex_div"].astype(float))

    vix = pd.read_parquet(DATA / "reference" / "vix.parquet")
    vix["date"] = pd.to_datetime(vix["date"])
    vix = vix.set_index("date")["vix_close"] / 100.0

    df = pd.DataFrame(index=main.index)
    df["iv_atm"] = main["atm_iv"]
    df["skew"] = main["skew_25d"]
    df["iv_strangle"] = main["iv_strangle"]
    if 60 in wide.columns and 7 in wide.columns:
        df["term_slope"] = wide[60] - wide[7]
    df["vix"] = vix.reindex(df.index)

    rv21 = r.rolling(21).apply(lambda x: np.sqrt(252 * np.mean(x ** 2)), raw=True)
    rv63 = r.rolling(63).apply(lambda x: np.sqrt(252 * np.mean(x ** 2)), raw=True)
    df["rv_trailing"] = rv21.reindex(df.index)
    df["vrp_now"] = df["iv_atm"] - df["rv_trailing"]
    df["rv_change"] = (rv21 - rv63).reindex(df.index)
    df["iv_z"] = ((df["iv_atm"] - df["iv_atm"].rolling(252).mean())
                  / df["iv_atm"].rolling(252).std())
    df["iv_change_5d"] = df["iv_atm"] - df["iv_atm"].shift(5)
    df["iv_vs_vix"] = df["iv_atm"] - df["vix"]

    df = df.join(ev.set_index("date")[["rv_forward", "vrp_realized_atm"]])
    return df.dropna()


def screen(df, target="vrp_realized_atm"):
    feats = [c for c in df.columns if c not in ("rv_forward", "vrp_realized_atm")]
    rows = []
    for f in feats:
        x, y = df[f], df[target]
        ic = x.corr(y, method="spearman")
        q = pd.qcut(x, 5, labels=False, duplicates="drop")
        by_q = y.groupby(q).mean()
        hit = y.groupby(q).apply(lambda s: (s > 0).mean())
        rows.append({
            "feature": f,
            "spearman_ic": round(float(ic), 4),
            "corr_rv_fwd": round(float(x.corr(df["rv_forward"], method="spearman")), 4),
            "q1_vrp": round(float(by_q.iloc[0]), 4),
            "q5_vrp": round(float(by_q.iloc[-1]), 4),
            "spread_q5_q1": round(float(by_q.iloc[-1] - by_q.iloc[0]), 4),
            "q1_hit": round(float(hit.iloc[0]), 3),
            "q5_hit": round(float(hit.iloc[-1]), 3),
        })
    return pd.DataFrame(rows).sort_values("spearman_ic", key=abs, ascending=False)


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)

    df = build()
    train = df[df.index <= TRAIN_END]
    test = df[df.index > TRAIN_END]

    print(f"train {len(train)} days  {train.index.min().date()} to {train.index.max().date()}")
    print(f"base rate: VRP positive {(train['vrp_realized_atm'] > 0).mean():.1%}\n")

    s = screen(train)
    print("feature screen on TRAINING data")
    print("  spearman_ic   : rank correlation with realized VRP")
    print("  spread_q5_q1  : mean VRP in top quintile minus bottom quintile")
    print("  q5_hit        : fraction of top-quintile days where VRP was positive\n")
    print(s.to_string(index=False))

    best = s.iloc[0]["feature"]
    print(f"\nquintile detail for '{best}'")
    q = pd.qcut(train[best], 5, labels=False, duplicates="drop")
    detail = train.groupby(q).agg(
        n=("vrp_realized_atm", "size"),
        mean_vrp=("vrp_realized_atm", "mean"),
        hit=("vrp_realized_atm", lambda s: (s > 0).mean()),
        mean_iv=("iv_atm", "mean"),
        mean_rv_fwd=("rv_forward", "mean"),
    ).round(4)
    print(detail.to_string())