import numpy as np
import pandas as pd
import pytest

from lsgamma.forecasting import FEATURE_FORECASTERS, FORECASTERS, HARGK, HARX, RF
from lsgamma.forecasting.HARX import FLOOR, TARGET, target, train
from lsgamma.pipeline.features import har_lags


@pytest.fixture
def feats():
    # constant 16% vol, VIX near 18
    rng = np.random.default_rng(0)
    n = 1500
    ret = pd.Series(rng.normal(0, 0.16 / np.sqrt(252), n),
                    index=pd.bdate_range("2010-01-01", periods=n))
    rv = (ret ** 2).rename("rv")
    return har_lags(rv).assign(ret=ret, vix=18 + rng.normal(0, 1, n))


def test_target_is_forward_mean(feats):
    t = target(feats)
    sq = feats["ret"] ** 2
    assert t.iloc[0] == pytest.approx(sq.iloc[1:1 + TARGET].mean())
    assert t.iloc[-TARGET:].isna().all()


def test_train_rows_never_use_unseen_days(feats):
    X, y = train(feats, ("vix", "ret_w"))
    assert X.index[-1] == feats.index[-TARGET - 1]
    assert list(X.columns) == ["rv_d", "rv_w", "rv_m", "vix", "ret_w"]


@pytest.mark.parametrize("cls", [HARGK, HARX, RF])
def test_forecast_near_true_vol(cls, feats):
    vol = cls().fit(feats).predict(TARGET)
    assert 0.13 < vol < 0.19


def test_at_moves_forecast_without_refit(feats):
    m = HARX().fit(feats.iloc[:1000])
    coef = m.coef.copy()
    a = m.predict()
    m.at(feats)
    assert m.coef.equals(coef)
    assert m.predict() != a


def test_floor():
    m = HARX()
    m.coef = pd.Series({"const": -1.0, "rv_d": 0, "rv_w": 0, "rv_m": 0, "vix": 0, "ret_w": 0})
    m.last = pd.Series({"rv_d": 0, "rv_w": 0, "rv_m": 0, "vix": 0, "ret_w": 0})
    assert m.predict() == pytest.approx(np.sqrt(FLOOR * 252))


def test_params(feats):
    assert set(HARGK().fit(feats).params()) == {"const", "rv_d", "rv_w", "rv_m"}
    imp = RF().fit(feats).params()
    assert sum(imp.values()) == pytest.approx(1.0)


def test_live_registry_unchanged():
    assert set(FORECASTERS) == {"garch", "har"}
    assert set(FEATURE_FORECASTERS) == {"har_gk", "harx", "rf"}
