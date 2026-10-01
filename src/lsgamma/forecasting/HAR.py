import numpy as np
import pandas as pd

from lsgamma.pipeline.features import har_lags

TRADING_DAYS = 252
FLOOR = 1e-10  # keeps forecast variance positive


class HAR:
    # HAR-RV forecaster on squared daily returns
    name = "har"

    def __init__(self):
        self.coef = None
        self.history = None

    def fit(self, returns):
        rv = pd.Series(returns).dropna() ** 2
        data = har_lags(rv).assign(target=rv.shift(-1)).dropna()
        X = np.column_stack([np.ones(len(data)), data[["rv_d", "rv_w", "rv_m"]]])
        self.coef = np.linalg.lstsq(X, data["target"].to_numpy(), rcond=None)[0]
        self.history = list(rv.iloc[-22:])
        return self

    def predict(self, horizon):
        h = list(self.history)
        out = []
        for _ in range(horizon):
            x = [1, h[-1], np.mean(h[-5:]), np.mean(h[-22:])]
            f = max(float(np.dot(self.coef, x)), FLOOR)
            out.append(f)
            h.append(f)
        return float(np.sqrt(np.mean(out) * TRADING_DAYS))

    def params(self):
        return dict(zip(["const", "beta_d", "beta_w", "beta_m"], map(float, self.coef)))
