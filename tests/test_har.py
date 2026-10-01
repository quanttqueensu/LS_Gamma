import numpy as np
import pandas as pd
import pytest

from lsgamma.forecasting import FORECASTERS, HAR


@pytest.fixture
def returns():
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(0, 0.01, 1000))


def test_har_predict(returns):
    vol = HAR().fit(returns).predict(21)
    assert isinstance(vol, float)
    assert 0.1 < vol < 0.25


def test_har_params(returns):
    assert set(HAR().fit(returns).params()) == {"const", "beta_d", "beta_w", "beta_m"}


def test_forecasters_interchangeable(returns):
    for cls in FORECASTERS.values():
        vol = cls().fit(returns).predict(10)
        assert isinstance(vol, float) and vol > 0
