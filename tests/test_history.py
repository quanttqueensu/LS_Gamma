from datetime import date

import numpy as np
import pandas as pd
import pytest

from lsgamma.history import build, marks, spot, trades

DAY = date(2024, 6, 12)
R = 0.05
EXPIRIES = {date(2024, 6, 12): 0.12, date(2024, 6, 14): 0.13, date(2024, 7, 12): 0.15}
E30 = date(2024, 7, 12)
MODEL = {"floor": 0.005, "bucket": [{"max_dte": 60, "a": 0.01, "b": 0.005}]}
CFG = build.load()


def true_iv(expiry, k):
    return EXPIRIES[expiry] - 0.1 * k + 0.8 * k * k


def path(seed=0):
    rng = np.random.default_rng(seed)
    secs = np.arange(23400 + 1800)
    ts = trades.at(DAY, "09:30") + pd.to_timedelta(secs, unit="s")
    return pd.Series(500 * np.exp(np.cumsum(rng.normal(0, 5e-5, len(secs)))), index=ts)


S = path()


def true_fwd(ts, expiry):
    return S.loc[ts].to_numpy() * np.exp(R * marks.years(ts, [expiry] * len(ts)))


def prints(ts, expiry, strike, right, rng):
    ts = pd.DatetimeIndex(ts)
    F = true_fwd(ts, expiry)
    T = marks.years(ts, [expiry] * len(ts))
    k = np.log(strike / F)
    px = marks.price(F, strike, T, R, true_iv(expiry, k), right == "C")
    return pd.DataFrame({"ts": ts, "expiry": expiry, "opt_type": right, "strike": strike,
                         "price": px, "size": rng.integers(1, 10, len(ts)).astype("uint32"),
                         "exchange": 300, "conditions": 209})


def synthetic(seed=1):
    rng = np.random.default_rng(seed)
    out = []
    for i, e in enumerate(EXPIRIES):
        t = S.index[i:23400:2]
        k = np.round(S.loc[t].to_numpy() + rng.integers(-2, 3, len(t)))
        out += [prints(t, e, k, np.array(["C"] * len(t)), rng),
                prints(t + pd.Timedelta(seconds=1), e, k, np.array(["P"] * len(t)), rng)]
        t2 = S.index[3 + i:23400:7]
        k2 = np.round(S.loc[t2].to_numpy() * np.exp(rng.uniform(-0.08, 0.08, len(t2))))
        out.append(prints(t2, e, k2, np.where(k2 > S.loc[t2].to_numpy(), "C", "P"), rng))
    df = pd.concat(out).sort_values("ts", kind="stable").reset_index(drop=True)
    return df[df["price"] >= 0.10].reset_index(drop=True)


TRADES = synthetic()


def daily_inputs():
    days = pd.bdate_range("2024-05-01", "2024-06-30")
    idx = pd.DataFrame({"irx": R * 100}, index=days)
    divs = pd.Series([1.5, 1.6], index=pd.to_datetime(["2024-03-15", "2024-06-21"]))
    seen = pd.DataFrame({"day": [date(2024, 6, 11), date(2024, 6, 3)], "expiry": [E30, E30],
                         "strike": [477.5, 470.0], "right": ["P", "C"]})
    return idx, divs, seen


def ctx_from(idx, divs, seen):
    return build.context(DAY, idx, divs, MODEL, seen)


CTX = ctx_from(*daily_inputs())


def garbage(df, rng):
    n = len(df)
    return df.assign(price=rng.choice([np.nan, 1e6, 0.5, 77.0], n),
                     strike=rng.uniform(100, 900, n).round(1),
                     expiry=[date(2024, 6, 12) + pd.Timedelta(days=int(d)).to_pytimedelta()
                             for d in rng.integers(0, 50, n)],
                     opt_type=rng.choice(["C", "P"], n),
                     conditions=rng.choice(CFG["conditions"], n))


def test_window_filters_codes_price_bounds_and_saturdays():
    t0 = trades.at(DAY, "10:00")
    df = pd.DataFrame({"ts": [t0, t0 + pd.Timedelta(seconds=1), t0 + pd.Timedelta(seconds=2),
                              t0 + pd.Timedelta(seconds=3)],
                       "expiry": [date(2014, 6, 21)] * 4, "conditions": [209, 232, 209, 219],
                       "price": [1.0, 1.0, 0.05, 2.0]})
    out = trades.window(df, t0, t0 + pd.Timedelta(seconds=3), CFG)
    assert out["price"].tolist() == [2.0]
    assert out["expiry"].iloc[0] == date(2014, 6, 20)


def test_implied_vol_round_trips():
    rng = np.random.default_rng(0)
    F = rng.uniform(80, 600, 500)
    K = F * np.exp(rng.uniform(-0.2, 0.2, 500))
    T = rng.uniform(1 / 365, 0.5, 500)
    sigma = rng.uniform(0.05, 1.0, 500)
    call = rng.random(500) > 0.5
    px = marks.price(F, K, T, R, sigma, call)
    iv = marks.implied(px, F, K, T, R, call)
    ok = ~np.isnan(iv)
    assert ok.mean() > 0.95
    assert np.allclose(iv[ok], sigma[ok], atol=1e-4)
    assert np.allclose(marks.price(F, K, T, R, iv, call)[ok], px[ok], atol=1e-9)
    assert np.isnan(marks.implied(np.array([0.0, 1e6]), 500, 500, 0.1, R, True)).all()


def test_greeks_match_finite_differences():
    S0, K, T, sig, h = 500.0, 505.0, 30 / 365, 0.2, 0.01
    for call in (True, False):
        def p(s=S0, t=T, v=sig):
            return marks.price(s * np.exp(R * t), K, t, R, v, call)
        g = marks.greeks(S0 * np.exp(R * T), K, T, R, sig, call)
        assert np.isclose(g["delta"], (p(S0 + h) - p(S0 - h)) / (2 * h), atol=1e-5)
        assert np.isclose(g["gamma"], (p(S0 + h) - 2 * p() + p(S0 - h)) / h ** 2, atol=1e-4)
        assert np.isclose(g["vega"], (p(v=sig + 1e-4) - p(v=sig - 1e-4)) / 2e-4 / 100, atol=1e-5)
        assert np.isclose(g["theta"], p(t=T - 1 / 365) - p(), atol=2e-3)


def test_parity_forward_and_spot_recover_truth():
    t = trades.at(DAY, "12:00")
    tr = trades.window(TRADES, trades.at(DAY, "09:30"), t, CFG)
    fw = spot.forwards(tr, R, spot.NO_DIVS, DAY, CFG)
    assert fw["near"] == DAY
    for e in EXPIRIES:
        # the 20-pair rolling median lags slightly
        assert np.isclose(spot.forward_at(fw, [t], [e])[0], true_fwd([t], e)[0], rtol=5e-4)
    assert abs(spot.spot(fw, t) - S.loc[t]) < 0.25


def pair_trades(t, F, n=6):
    rows = []
    for i in range(n):
        ts, K = t + pd.Timedelta(seconds=2 * i), 500.0 + i - n // 2
        rows += [(ts, DAY, "C", K, max(F - K, 0) + 1.0), (ts, DAY, "P", K, max(K - F, 0) + 1.0)]
    df = pd.DataFrame(rows, columns=["ts", "expiry", "opt_type", "strike", "price"])
    return df.assign(size=1, exchange=300, conditions=209)


def test_spot_carries_forward_and_never_interpolates():
    cfg = {**CFG, "fwd_pairs": 3, "min_pairs": 1}
    df = pd.concat([pair_trades(trades.at(DAY, "10:00"), 500.0),
                    pair_trades(trades.at(DAY, "11:00"), 510.0)], ignore_index=True)
    fw = spot.forwards(df, 0.0, spot.NO_DIVS, DAY, cfg)
    assert spot.spot(fw, trades.at(DAY, "10:30")) == pytest.approx(500.0)
    assert spot.spot(fw, trades.at(DAY, "11:30")) == pytest.approx(510.0)
    assert np.isnan(spot.spot(fw, trades.at(DAY, "09:45")))
    early = spot.forwards(df[df["ts"] < trades.at(DAY, "10:30")], 0.0, spot.NO_DIVS, DAY, cfg)
    assert spot.spot(early, trades.at(DAY, "10:30")) == spot.spot(fw, trades.at(DAY, "10:30"))


def test_parity_close_near_true_close():
    close = spot.parity_close(TRADES, DAY, R, CFG)
    assert abs(close - S.loc[trades.at(DAY, "15:59:59")]) < 0.1


def test_decide_smile_recovers_known_iv():
    asof = trades.at(DAY, "12:15")
    ch = build.snapshot(TRADES, CTX, asof, CFG)["chain"]
    cut = asof - pd.Timedelta(CFG["lag"])
    for e in [date(2024, 6, 14), E30]:
        rows = ch[ch["expiry"] == e]
        k = np.log(rows["strike"] / true_fwd([cut], e)[0])
        inside = k.abs() < 0.07
        assert np.abs(rows["iv"] - true_iv(e, k))[inside].max() < 0.003
    assert np.allclose(ch["und_price"], S.loc[cut], atol=0.25)
    assert set(ch.columns) == set(marks.COLUMNS)
    assert isinstance(ch["expiry"].iloc[0], date) and (ch["dte"] >= CFG["min_dte"]).all()
    assert (ch["bid"] < ch["mid"]).all() and (ch["mid"] < ch["ask"]).all()


def test_decide_view_ignores_everything_after_cutoff():
    asof = trades.at(DAY, "12:15")
    cut = asof - pd.Timedelta(CFG["lag"])
    rng = np.random.default_rng(7)
    late = TRADES["ts"] > cut
    poisoned = pd.concat([TRADES[~late], garbage(TRADES[late], rng),
                          garbage(TRADES[late].sample(5000, random_state=1), rng)])
    poisoned = poisoned.sort_values("ts", kind="stable").reset_index(drop=True)
    idx, divs, seen = daily_inputs()
    after = idx.index >= pd.Timestamp(DAY)
    idx.loc[after, "irx"] = 99.0
    divs = pd.concat([divs[divs.index < pd.Timestamp(DAY)],
                      pd.Series([50.0], index=pd.to_datetime(["2024-06-13"]))])
    seen = pd.concat([seen, pd.DataFrame({"day": [DAY], "expiry": [E30], "strike": [600.0],
                                          "right": ["C"]})])
    a = build.snapshot(TRADES, CTX, asof, CFG)
    b = build.snapshot(poisoned, ctx_from(idx, divs, seen), asof, CFG)
    pd.testing.assert_frame_equal(a["chain"], b["chain"])
    pd.testing.assert_frame_equal(a["atm_iv"], b["atm_iv"])


def test_fill_view_uses_only_fill_window_prices():
    asof = trades.at(DAY, "12:15")
    cut = asof - pd.Timedelta(CFG["lag"])
    end = asof + pd.Timedelta(CFG["fill_window"])
    rng = np.random.default_rng(8)
    ts = TRADES["ts"]
    before, gap, inside = ts <= cut, (ts > cut) & (ts <= asof), (ts > asof) & (ts <= end)
    old = TRADES[before].assign(price=rng.uniform(0.1, 1e4, before.sum()))
    poisoned = pd.concat([old, garbage(TRADES[gap], rng), TRADES[inside],
                          garbage(TRADES[ts > end], rng)])
    poisoned = poisoned.sort_values("ts", kind="stable").reset_index(drop=True)
    a = build.snapshot(TRADES, CTX, asof, CFG)["fill"]
    b = build.fill(poisoned, CTX, asof, CFG)
    pd.testing.assert_frame_equal(a, b)
    assert a["mid"].notna().mean() > 0.9 and (a["src"] == "fill_smile").all()
    assert abs(a["und_price"].median() - S.loc[end]) < 0.25


def test_fill_falls_back_to_decide_smile_and_ignores_later_trades():
    asof = trades.at(DAY, "12:15")
    end = asof + pd.Timedelta(CFG["fill_window"])
    ts = TRADES["ts"]
    thin = TRADES[~((ts > asof) & (ts <= end) & (TRADES["expiry"] == E30))]
    rng = np.random.default_rng(9)
    late = thin["ts"] > end
    poisoned = pd.concat([thin[~late], garbage(thin[late], rng)])
    poisoned = poisoned.sort_values("ts", kind="stable").reset_index(drop=True)
    a = build.snapshot(thin, CTX, asof, CFG)["fill"]
    pd.testing.assert_frame_equal(a, build.fill(poisoned, CTX, asof, CFG))
    rows = a[a["expiry"] == E30]
    assert (rows["src"] == "decide_smile").all() and rows["mid"].notna().all()
    assert (a.loc[a["expiry"] != E30, "src"] == "fill_smile").all()


def test_fill_forward_carries_from_open_without_window_pairs():
    asof = trades.at(DAY, "12:15")
    end = asof + pd.Timedelta(CFG["fill_window"])
    ts = TRADES["ts"]
    df = TRADES[~((ts > asof) & (ts <= end))]
    f = build.snapshot(df, CTX, asof, CFG)["fill"]
    assert len(f) and f["mid"].notna().all() and (f["src"] == "decide_smile").all()
    assert abs(f["und_price"].median() - S.loc[asof]) < 0.5


def test_held_deep_contracts_stay_listed_above_intrinsic():
    held = pd.DataFrame({"expiry": [E30, E30], "strike": [600.0, 400.0], "right": ["P", "C"]})
    ctx = {**CTX, "contracts": pd.concat([CTX["contracts"], held], ignore_index=True)}
    snap = build.snapshot(TRADES, ctx, trades.at(DAY, "12:15"), CFG)
    for view in (snap["chain"], snap["fill"]):
        for k, right in [(600.0, "P"), (400.0, "C")]:
            row = view[(view["expiry"] == E30) & (view["strike"] == k) & (view["right"] == right)]
            s = row["und_price"].iloc[0]
            assert len(row) == 1 and row["mid"].iloc[0] >= abs(k - s) - 1e-9


def test_universe_keeps_recent_contracts_and_skips_future_ones():
    late = prints(S.index[10000:10060], E30, 521.5, np.array(["C"] * 60), np.random.default_rng(2))
    df = pd.concat([TRADES, late]).sort_values("ts", kind="stable").reset_index(drop=True)
    first = late["ts"].min()
    before = build.snapshot(df, CTX, first + pd.Timedelta(minutes=14), CFG)
    after = build.snapshot(df, CTX, first + pd.Timedelta(minutes=16), CFG)
    for snap in (before, after):
        rows = snap["chain"][snap["chain"]["expiry"] == E30]
        assert ((rows["strike"] == 477.5) & (rows["right"] == "P")).any()
        assert ((rows["strike"] == 470.0) & (rows["right"] == "C")).any()
        assert ((snap["fill"]["strike"] == 477.5) & (snap["fill"]["right"] == "P")).any()
    assert not (before["chain"]["strike"] == 521.5).any()
    assert not (before["fill"]["strike"] == 521.5).any()
    assert (after["chain"]["strike"] == 521.5).any()


def test_failed_smiles_skip_decide_and_blank_fill():
    cfg = {**CFG, "smile_min_trades": 10 ** 9}
    asof = trades.at(DAY, "12:15")
    with pytest.raises(build.Skip):
        build.snapshot(TRADES, CTX, asof, cfg)
    f = build.fill(TRADES, CTX, asof, cfg)
    assert len(f) and f["mid"].isna().all() and f["und_price"].notna().all()


def test_projected_dividends_use_only_past_ex_dates():
    divs = pd.Series([1.5, 1.6], index=pd.to_datetime(["2024-03-15", "2024-06-21"]))
    p = build.projected(divs, DAY)
    assert list(p.index) == [date(2024, 6, 21), date(2024, 9, 20)] and (p == 1.5).all()


def test_no_trade_days_are_recorded(monkeypatch, tmp_path):
    monkeypatch.setattr(build.r2, "trades", lambda day: TRADES.iloc[:0])
    assert build.build_day(DAY, CTX, CFG, tmp_path)[2][0]["why"] == "no_trades"


def test_calendar_is_crsp_days_then_traded_weekdays():
    crsp = pd.DataFrame({"dlycaldt": pd.to_datetime(["2024-06-11", "2024-06-12"])})
    assert build.days(crsp, "2024-06-12", "2024-06-12") == [DAY]


def test_manifest_refuses_other_settings_even_with_force(tmp_path):
    (tmp_path / "manifest.json").write_text('{"config_hash": "abc", "builds": []}')
    build.check_version(tmp_path, "abc")
    with pytest.raises(SystemExit):
        build.check_version(tmp_path, "def")
    assert build.config_hash({"a": 1}, MODEL) != build.config_hash({"a": 2}, MODEL)


def test_source_hash_ignores_comments_not_code(tmp_path):
    for rel in build.SOURCES:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text((build.PKG / rel).read_text())
    base = build.sources(tmp_path)
    feats = tmp_path / "pipeline" / "features.py"
    feats.write_text(feats.read_text() + "\n\n# a comment\n")
    assert build.sources(tmp_path) == base
    feats.write_text(feats.read_text().replace("TRADING_DAYS = 252", "TRADING_DAYS = 251"))
    assert build.sources(tmp_path) != base


def test_build_refuses_dirty_tree_for_configured_version(monkeypatch):
    monkeypatch.setattr(build, "dirty", lambda: True)
    with pytest.raises(SystemExit, match="uncommitted"):
        build.build(str(DAY), str(DAY), CFG)


def test_build_refuses_dates_after_last_day():
    after = pd.Timestamp(CFG["last_day"]) + pd.Timedelta(days=1)
    with pytest.raises(SystemExit):
        build.main(["--start", CFG["last_day"], "--end", str(after.date())])
