import numpy as np
import pandas as pd

from lsgamma.history import daily


def crsp(n=300, seed=0):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-01-01", periods=n)
    retx = rng.normal(0, 0.01, n)
    div = np.where(np.arange(n) % 63 == 40, 1.8, 0.0)
    close = 500 * np.cumprod(1 + retx)
    ret = retx + div / np.r_[500, close[:-1]]
    return pd.DataFrame({
        "dlycaldt": days.date, "dlyopen": close * 0.999, "dlyhigh": close * 1.01,
        "dlylow": close * 0.99, "dlyclose": close, "dlyvol": 1e6, "dlyret": ret,
        "dlyretx": retx, "dlyorddivamt": np.where(div > 0, div, np.nan)})


def test_adjusted_close_returns_equal_dlyret():
    c = crsp()
    out = daily.spy(c)
    assert np.allclose(out["close"].pct_change().iloc[1:], c["dlyret"].iloc[1:])
    assert np.isclose(out["close"].iloc[-1], c["dlyclose"].iloc[-1])
    assert np.allclose(out["open"] / out["close"], 0.999)
    assert list(out.columns) == ["open", "high", "low", "close", "volume", "dividend"]
    assert out.index.name == "date" and out.index.tz is None


def test_parity_splice_is_continuous():
    c = crsp()
    last = c["dlyclose"].iloc[-1]
    days = pd.bdate_range(pd.Timestamp(c["dlycaldt"].iloc[-1]) + pd.Timedelta(days=1), periods=5)
    parity = pd.Series(last * np.array([1.01, 1.0, 0.98, 0.99, 1.02]), index=days)
    out = daily.spy(c, parity)
    ret = out["close"].pct_change()
    assert np.allclose(ret.loc[days], parity.pct_change().fillna(0.01))
    assert np.allclose(ret.iloc[1:len(c)], c["dlyret"].iloc[1:])
    tail = out.loc[days]
    assert np.allclose(tail["open"], tail["close"]) and np.allclose(tail["high"], tail["low"])


def test_dividends_by_ex_date():
    d = daily.dividends(crsp())
    assert (d == 1.8).all() and len(d) == 5


def indices_inputs():
    days = pd.bdate_range("2026-01-01", "2026-08-31")
    cboe = pd.DataFrame({"date": days[days <= "2026-06-30"].date, "vix": 15.0})
    ff = pd.DataFrame({"date": days[days <= "2026-04-30"].date, "rf": 0.0002})
    yf = pd.DataFrame({"vix9d": 14.0, "vix3m": 17.0, "vvix": 90.0}, index=days)
    return cboe, ff, yf


def test_irx_from_rf_is_annual_percent():
    assert np.isclose(daily.irx_from_rf(0.0002), ((1.0002) ** 252 - 1) * 100)


def test_ff_forward_fill_stops_at_last_day():
    idx = daily.indices(*indices_inputs())
    assert idx.index.max() == pd.Timestamp("2026-07-10")
    assert idx["irx"].notna().all()
    assert np.isclose(idx.loc["2026-07-10", "irx"], daily.irx_from_rf(0.0002))
    assert idx.loc["2026-07-01":, "vix"].isna().all()
    assert list(idx.columns) == ["vix", "vix9d", "vix3m", "vvix", "irx"]


def test_indices_drop_null_duplicate_dates():
    cboe, ff, yf = indices_inputs()
    dup = cboe.head(3).assign(vix=np.nan)
    idx = daily.indices(pd.concat([dup, cboe], ignore_index=True), ff, yf)
    assert idx.index.is_unique
    assert (idx.loc[:"2026-06-30", "vix"] == 15.0).all()


def test_features_drop_vix_after_cboe_ends():
    c = crsp(400)
    c["dlycaldt"] = pd.bdate_range("2025-01-01", periods=400).date
    c = c[pd.to_datetime(c["dlycaldt"]) <= "2026-07-31"]
    feats = daily.features(daily.spy(c), daily.indices(*indices_inputs()))
    assert feats.loc["2026-07-01":, "vix"].isna().all()
    assert feats.loc["2026-06-30", "vix"] == 15.0
    assert feats.loc["2026-07-01":, "rf"].notna().all()


def test_trades_reads_one_eastern_day(tmp_path, monkeypatch):
    from datetime import date
    from lsgamma.history import r2
    ts = pd.to_datetime(["2024-06-11 23:59", "2024-06-12 00:00", "2024-06-12 16:15",
                         "2024-06-13 00:00"]).tz_localize("America/New_York")
    pd.DataFrame({"ts": ts, "underlying": "SPY", "expiry": date(2024, 6, 21),
                  "opt_type": "C", "strike": 540.0, "price": 1.0,
                  "size": np.uint32(1), "exchange": np.uint16(5),
                  "conditions": ["209", "209", "", "219"], "osi": "x"}
                 ).to_parquet(tmp_path / "2024-06.parquet")
    monkeypatch.setattr(r2, "OPTIONS", tmp_path)
    out = r2.trades("2024-06-12")
    assert len(out) == 2 and list(out["conditions"]) == [209, 0]
    assert str(out["ts"].dt.tz) == "America/New_York"
    assert out["expiry"].iloc[0] == date(2024, 6, 21)
