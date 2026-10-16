import math

import pandas as pd

TRADING_DAYS = 252
GAPS = ["skipped", "no_fill", "no_delta", "no_mark"]


def daily_pnl(equity):
    if equity.empty:
        return pd.Series(dtype=float)
    eq = equity.groupby("date")["equity"].last()
    return eq.diff().fillna(eq.iloc[0])


def sharpe(daily, capital):
    r = daily / capital
    sd = r.std()
    return float(r.mean() / sd * math.sqrt(TRADING_DAYS)) if sd > 0 else math.nan


def max_drawdown(daily):
    eq = daily.cumsum()
    return float((eq.cummax().clip(lower=0) - eq).max()) if len(eq) else 0.0


def expected_shortfall(daily, q=0.05):
    if daily.empty:
        return math.nan
    return float(daily[daily <= daily.quantile(q)].mean())


def pairs(trades):
    # match each close to its open
    o = trades[trades["action"] == "open"].reset_index(drop=True)
    c = trades[trades["action"] == "close"].reset_index(drop=True)
    if "entry_ts" not in c or c["entry_ts"].isna().any():
        return o.iloc[:len(c)], c
    o = o.set_index("ts").loc[c["entry_ts"]].reset_index()
    return o, c


def holding_days(trades):
    if trades.empty:
        return math.nan
    o, c = pairs(trades)
    opens, closes = o["date"].map(pd.Timestamp).tolist(), c["date"].map(pd.Timestamp).tolist()
    days = [(c - o).days for o, c in zip(opens, closes)]
    return float(sum(days) / len(days)) if days else math.nan


def gaps(events, equity):
    count = events["event"].value_counts() if len(events) else pd.Series(dtype=int)
    n = {k: int(count.get(k, 0)) for k in GAPS}
    scheduled = len(equity) + n["skipped"]
    return {**n, **{f"{k}_share": n[k] / scheduled if scheduled else math.nan for k in GAPS}}


def decide_smile_share(trades):
    if trades.empty:
        return math.nan
    src = trades["src"] if "src" in trades else pd.Series("fill_smile", index=trades.index)
    fills = src[src.isin(["fill_smile", "decide_smile"])]
    return float((fills == "decide_smile").mean()) if len(fills) else math.nan


def summary(out, cfg):
    daily = daily_pnl(out["equity"])
    trades = out["trades"]
    closes = trades[trades["action"] == "close"] if len(trades) else trades
    return {"pnl": float(daily.sum()) if len(daily) else 0.0,
            "sharpe": sharpe(daily, cfg["size"]["capital"]),
            "max_dd": max_drawdown(daily),
            "es_5": expected_shortfall(daily),
            "trades": len(closes),
            "win_rate": float((closes["pnl_net"] > 0).mean()) if len(closes) else math.nan,
            "hold_days": holding_days(trades),
            "decide_smile": decide_smile_share(trades),
            **gaps(out["events"], out["equity"])}
