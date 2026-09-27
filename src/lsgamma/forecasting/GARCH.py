import numpy as np
import pandas as pd
from arch import arch_model

TRADING_DAYS = 252
SCALE = 100  # arch fits better on percent returns


class GARCH:
    # GARCH(1,1) forecaster for realized volatility
    name = "garch"

    def __init__(self, p=1, q=1):
        self.p = p
        self.q = q
        self.result = None

    def fit(self, returns):
        # Fit model on daily log returns
        r = pd.Series(returns).dropna() * SCALE
        model = arch_model(r, mean="Zero", vol="GARCH", p=self.p, q=self.q)
        self.result = model.fit(disp="off")
        return self

    def predict(self, horizon):
        # Average daily variance over the horizon
        var = self.result.forecast(horizon=horizon, reindex=False).variance.iloc[-1].mean()
        # Annualize and convert back to decimals
        return float(np.sqrt(var * TRADING_DAYS) / SCALE)

    def params(self):
        # Fitted omega, alpha and beta values
        return self.result.params.to_dict()
