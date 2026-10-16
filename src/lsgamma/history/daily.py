import pandas as pd

from lsgamma.pipeline.features import build_features

LAST_DAY = "2026-07-10"
TRADING_DAYS = 252
VIX_COLS = ["vix", "vix9d_vix", "vix_vix3m", "vix_pct_1y"]


def _dated(df, col):
    df = df.copy()
    df.index = pd.to_datetime(df.pop(col)).rename("date")
    return df.sort_index()


def _raw(crsp, parity_close):
    c = _dated(crsp, "dlycaldt").astype(float)
    raw = pd.DataFrame({"open": c["dlyopen"], "high": c["dlyhigh"], "low": c["dlylow"],
                        "close": c["dlyclose"], "volume": c["dlyvol"],
                        "dividend": c["dlyorddivamt"].fillna(0.0), "ret": c["dlyret"]})
    if parity_close is None or parity_close.empty:
        return raw
    p = parity_close.astype(float).copy()
    p.index = pd.to_datetime(p.index).rename("date")
    p = p[p.index > raw.index[-1]].sort_index()
    ret = pd.concat([raw["close"].iloc[-1:], p]).pct_change().iloc[1:]
    # parity rows: price-only returns, flat OHLC
    extra = pd.DataFrame({"open": p, "high": p, "low": p, "close": p,
                          "volume": float("nan"), "dividend": 0.0, "ret": ret})
    return pd.concat([raw, extra])


def spy(crsp, parity_close=None):
    raw = _raw(crsp, parity_close)
    growth = (1 + raw["ret"].fillna(0.0)).cumprod()
    adj = growth / growth.iloc[-1] * raw["close"].iloc[-1]
    factor = adj / raw["close"]
    out = raw[["open", "high", "low"]].mul(factor, axis=0)
    out["close"] = adj
    out["volume"] = raw["volume"]
    out["dividend"] = raw["dividend"]
    return out


def irx_from_rf(rf):
    return ((1 + rf) ** TRADING_DAYS - 1) * 100


def indices(cboe, ff, yf, last_day=LAST_DAY):
    vix = _dated(cboe.dropna(subset=["vix"]), "date")["vix"].astype(float)
    vix = vix[~vix.index.duplicated(keep="last")]
    rf = _dated(ff.dropna(subset=["rf"]), "date")["rf"].astype(float)
    irx = irx_from_rf(rf[~rf.index.duplicated(keep="last")]).rename("irx")
    yf = yf.copy()
    yf.index = pd.to_datetime(yf.index).rename("date")
    df = pd.concat([vix, yf[["vix9d", "vix3m", "vvix"]].astype(float), irx], axis=1)
    df = df.sort_index().loc[:pd.Timestamp(last_day)]
    df["irx"] = df["irx"].ffill()
    return df[["vix", "vix9d", "vix3m", "vvix", "irx"]]


def features(spy, idx):
    feats = build_features(spy, idx)
    # build_features ffills; no VIX past CBOE end
    feats.loc[feats.index > idx["vix"].last_valid_index(), VIX_COLS] = float("nan")
    return feats


def dividends(crsp):
    d = _dated(crsp, "dlycaldt")["dlyorddivamt"].astype(float)
    return d[d > 0].rename("dividend")
