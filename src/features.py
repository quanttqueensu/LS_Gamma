from pathlib import Path

import numpy as np
import pandas as pd

from Data.pipeline import forecast as fc

DATA = Path(__file__).resolve().parent / "Data" / "data"
PRIMARY_TENOR = 28
TRADING_DAYS = 252.0
IV_Z_WINDOW = 252
RV_LONG_MULTIPLE = 3
GARCH_REFIT_EVERY = 21
GARCH_CACHE_NAME = "rv_forecast_garch.parquet"

# ex-ante sign convention: spread_* = rv - iv, positive means vol looks cheap.
# the eval file's vrp_realized_* runs the other way. see Classification.py.

_FEATURES = {}


def feature(fn):
    _FEATURES[fn.__name__] = fn
    return fn


def available():
    return list(_FEATURES)


def to_dates(s):
    return pd.to_datetime(pd.Series(s).to_numpy(), errors="coerce")


def daily_signal(data_dir=DATA, tenor=PRIMARY_TENOR):
    df = pd.read_parquet(Path(data_dir) / "signals" / "daily_signal.parquet")
    df = df[df["target_dte"] == tenor].copy()
    df["date"] = to_dates(df["date"])
    return df.sort_values("date").set_index("date")


def spy_returns(data_dir=DATA):
    spy = pd.read_parquet(Path(data_dir) / "reference" / "spy_daily.parquet",
                          columns=["date", "ret_ex_div"])
    spy["date"] = to_dates(spy["date"])
    spy = spy.sort_values("date").set_index("date")
    return np.log1p(spy["ret_ex_div"].astype(float))


def rolling_vol(returns, window):
    return np.sqrt(TRADING_DAYS * (returns ** 2).rolling(window).mean())


def garch_forecast(data_dir=DATA, tenor=PRIMARY_TENOR,
                   refit_every=GARCH_REFIT_EVERY, force=False):
    cache = Path(data_dir) / "signals" / GARCH_CACHE_NAME
    if cache.exists() and not force:
        c = pd.read_parquet(cache)
        return c.set_index(to_dates(c["date"]))["rv_forecast_garch"]

    # imported lazily so the scipy dependency is only paid on a cache miss
    from Forecast_Models.garch import forecast_series, load_returns

    dates, returns = load_returns(Path(data_dir) / "reference" / "spy_daily.parquet")
    s = forecast_series(dates, returns, fc.trading_days_for(tenor),
                        refit_every=refit_every)
    s.index = to_dates(s.index)
    s = s.rename("rv_forecast_garch")

    cache.parent.mkdir(parents=True, exist_ok=True)
    s.rename_axis("date").reset_index().to_parquet(cache, index=False)
    return s


class Context:
    def __init__(self, data_dir=DATA, tenor=PRIMARY_TENOR):
        self.data_dir = Path(data_dir)
        self.tenor = tenor
        self.signal = daily_signal(data_dir, tenor)
        self.returns = spy_returns(data_dir)
        self._cache = {}

    @property
    def index(self):
        return self.signal.index

    def col(self, name):
        return self.signal[name].astype(float)

    def garch(self):
        if "garch" not in self._cache:
            self._cache["garch"] = (garch_forecast(self.data_dir, self.tenor)
                                    .reindex(self.index))
        return self._cache["garch"]

    def vol(self, window):
        key = ("vol", window)
        if key not in self._cache:
            self._cache[key] = rolling_vol(self.returns, window).reindex(self.index)
        return self._cache[key]

    def rv_window(self):
        return int(self.signal["rv_window_days"].iloc[0])


@feature
def iv_atm(ctx):
    return ctx.col("iv_atm")


@feature
def iv_strangle(ctx):
    return ctx.col("iv_strangle")


@feature
def skew(ctx):
    return ctx.col("skew")


@feature
def term_slope(ctx):
    return ctx.col("term_slope")


@feature
def vix(ctx):
    return ctx.col("vix")


@feature
def rv_trailing(ctx):
    # the pipeline's backward window for this tenor, so trailing and
    # forward vol are measured over the same span
    return ctx.col("rv_backward")


@feature
def rv_forecast_ewma(ctx):
    return ctx.col("rv_forecast")


@feature
def rv_forecast_garch(ctx):
    return ctx.garch()


@feature
def rv_change(ctx):
    return ctx.col("rv_backward") - ctx.vol(RV_LONG_MULTIPLE * ctx.rv_window())


@feature
def iv_z(ctx):
    v = ctx.col("iv_atm")
    return (v - v.rolling(IV_Z_WINDOW).mean()) / v.rolling(IV_Z_WINDOW).std()


@feature
def iv_change_5d(ctx):
    return ctx.col("iv_atm").diff(5)


@feature
def iv_vs_vix(ctx):
    return ctx.col("iv_atm") - ctx.col("vix")


@feature
def spread_trailing(ctx):
    return ctx.col("rv_backward") - ctx.col("iv_atm")


@feature
def spread_ewma(ctx):
    return ctx.col("rv_forecast") - ctx.col("iv_atm")


@feature
def spread_garch(ctx):
    return ctx.garch() - ctx.col("iv_atm")


def features(data_dir=DATA, tenor=PRIMARY_TENOR, names=None, ctx=None):
    ctx = ctx or Context(data_dir, tenor)
    names = list(names or available())
    unknown = [n for n in names if n not in _FEATURES]
    if unknown:
        raise KeyError(f"unknown features {unknown}; have {available()}")
    return pd.DataFrame({n: _FEATURES[n](ctx) for n in names}, index=ctx.index)


def targets(data_dir=DATA, tenor=PRIMARY_TENOR):
    ev = pd.read_parquet(Path(data_dir) / "signals" /
                         "realized_forward_EVALUATION_ONLY.parquet")
    ev = ev[ev["target_dte"] == tenor].copy()
    ev["date"] = to_dates(ev["date"])
    ev = ev.sort_values("date").set_index("date")

    t = pd.DataFrame(index=ev.index)
    t["rv_forward"] = ev["rv_forward"].astype(float)
    t["vrp_realized_atm"] = ev["vrp_realized_atm"].astype(float)
    # negated into the ex-ante convention the model fits in
    t["spread_realized_atm"] = -t["vrp_realized_atm"]
    t["spread_realized_strangle"] = -ev["vrp_realized_strangle"].astype(float)
    t["n_days_ahead"] = ev["n_days_ahead"].astype(float)
    return t


def aligned(data_dir=DATA, tenor=PRIMARY_TENOR, names=None):
    return features(data_dir, tenor, names).join(targets(data_dir, tenor),
                                                 how="inner")
