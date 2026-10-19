import pandas as pd

from lsgamma.forecasting.HARX import TARGET, inputs, to_vol, train

TREES = 300
LEAF = 20  # fixed, not tuned


class RF:
    # random forest on the HAR-X inputs
    name = "rf"
    exog = ("vix", "ret_w")

    def __init__(self, seed=0):
        self.seed = seed
        self.model = None
        self.last = None

    def fit(self, feats):
        from sklearn.ensemble import RandomForestRegressor  # research only
        X, y = train(feats, self.exog)
        self.model = RandomForestRegressor(n_estimators=TREES, min_samples_leaf=LEAF,
                                           random_state=self.seed, n_jobs=-1).fit(X, y)
        self.cols = list(X.columns)
        return self.at(feats)

    def at(self, feats):
        self.last = inputs(feats, self.exog).iloc[[-1]]
        return self

    def predict(self, horizon=TARGET):
        return to_vol(float(self.model.predict(self.last[self.cols])[0]))

    def params(self):
        return dict(zip(self.cols, map(float, self.model.feature_importances_)))
