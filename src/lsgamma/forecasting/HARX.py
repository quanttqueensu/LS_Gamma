import numpy as np
import pandas as pd

TRADING_DAYS = 252
TARGET = 22  # trading days ahead, fixed
FLOOR = 0.05 ** 2 / TRADING_DAYS  # 5% vol floor


def inputs(feats, exog):
    # HAR lags on Garman-Klass RV, plus extras
    x = feats[["rv_d", "rv_w", "rv_m"]].copy()
    if "vix" in exog:
        x["vix"] = (feats["vix"] / 100) ** 2 / TRADING_DAYS
    if "ret_w" in exog:
        x["ret_w"] = feats["ret"].rolling(5).sum()
    return x


def target(feats, h=TARGET):
    # mean squared return over the next h days
    sq = feats["ret"] ** 2
    return sq[::-1].rolling(h).mean()[::-1].shift(-1).rename("target")


def train(feats, exog):
    data = inputs(feats, exog).join(target(feats)).dropna()
    return data.drop(columns="target"), data["target"]


def to_vol(var):
    return float(np.sqrt(max(var, FLOOR) * TRADING_DAYS))


class HARX:
    # direct 22-day HAR with VIX, weekly return
    name = "harx"
    exog = ("vix", "ret_w")

    def __init__(self):
        self.coef = None
        self.last = None

    def fit(self, feats):
        X, y = train(feats, self.exog)
        A = np.column_stack([np.ones(len(X)), X])
        self.coef = pd.Series(np.linalg.lstsq(A, y.to_numpy(), rcond=None)[0],
                              index=["const", *X.columns])
        return self.at(feats)

    def at(self, feats):
        # newest completed day, same fit
        self.last = inputs(feats, self.exog).iloc[-1]
        return self

    def predict(self, horizon=TARGET):
        return to_vol(self.coef["const"] + float(self.coef.drop("const") @ self.last))

    def params(self):
        return self.coef.to_dict()


class HARGK(HARX):
    # direct 22-day HAR on Garman-Klass RV
    name = "har_gk"
    exog = ()
