import sys

import numpy as np
import pandas as pd

from Forecast_Models import vrp_model as V

N = 800
CUT = 600
WIN = 19


def synthetic(seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.15, 0.04, N)
    y = 0.5 * x - 0.05 + rng.normal(0.0, 0.02, N)
    return pd.DataFrame(
        {"iv_atm": x, V.TARGET: y},
        index=pd.date_range("2015-01-02", periods=N, freq="B"),
    )


def corrupt_future(df, cut=CUT):
    out = df.copy()
    out.iloc[cut:, out.columns.get_loc(V.TARGET)] = 999.0
    return out


def leaky_mask(n, i, win):
    # the bug this suite exists to catch: uses every row up to i, including
    # rows whose forward window has not closed yet
    return np.arange(n) <= i


def test_embargo_mask():
    m = V.embargo_mask(10, 5, 3)
    assert m.tolist() == [True] * 3 + [False] * 7


def test_no_lookahead():
    df = synthetic()
    a = V.predict_pit(df, ["iv_atm"], win=WIN)
    b = V.predict_pit(corrupt_future(df), ["iv_atm"], win=WIN)
    safe = slice(0, CUT + WIN)
    np.testing.assert_allclose(a[safe].to_numpy(), b[safe].to_numpy(),
                               equal_nan=True)


def test_leak_is_detected():
    df = synthetic()
    a = V.predict_pit(df, ["iv_atm"], win=WIN, mask_fn=leaky_mask)
    b = V.predict_pit(corrupt_future(df), ["iv_atm"], win=WIN,
                      mask_fn=leaky_mask)
    safe = slice(0, CUT + WIN)
    diff = np.nanmax(np.abs(a[safe].to_numpy() - b[safe].to_numpy()))
    assert diff > 1e-6, "leaky mask went undetected; the test has no teeth"


def test_constant_spec_is_trailing_mean():
    df = synthetic()
    p = V.predict_pit(df, [], win=WIN, refit_every=1)
    i = N - 1
    usable = np.isfinite(df[V.TARGET].to_numpy()) & V.embargo_mask(N, i, WIN)
    assert np.isclose(p.iloc[i], df[V.TARGET].to_numpy()[usable].mean())


def test_hac_se_exceeds_ols_under_overlap():
    df = synthetic()
    d = df.dropna()
    X, y = V.design(d, ["iv_atm"]), d[V.TARGET].to_numpy(float)
    beta = V.fit(X, y)
    resid = y - X @ beta
    hac = np.sqrt(np.diag(V.hac_cov(X, resid, WIN)))
    ols = np.sqrt(np.diag(np.linalg.pinv(X.T @ X) * (resid @ resid) / (len(y) - X.shape[1])))
    assert np.all(hac > 0) and np.all(ols > 0)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  pass  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
