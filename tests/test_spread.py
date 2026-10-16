import numpy as np
import pandas as pd

from lsgamma.history import spread

COEF = {0: (0.004, 0.004), 1: (0.003, 0.005), 2: (0.002, 0.006)}
TIER = {1: ((0.05, 0.005), (0.82, 0.9)), 2: ((0.5, 0.02), (0.91, 1.0))}


def chain(asof, n=400, iv=0.2, seed=0, tier=0):
    rng = np.random.default_rng(seed)
    dte = rng.integers(1, 61, n)
    mid = rng.uniform(0.2, 20, n) + 20 * tier
    coef = [TIER[tier][0] if tier else COEF[i] for i in spread.bucket(dte)]
    a, b = np.array(coef).T
    half = a + b * mid + rng.laplace(0, 0.0005, n)
    delta = rng.uniform(*TIER[tier][1], n) if tier else rng.uniform(-0.7, 0.7, n)
    return pd.DataFrame({"asof": pd.Timestamp(asof, tz="America/New_York"), "dte": dte,
                         "bid": mid - half, "ask": mid + half, "mid": mid, "iv": iv,
                         "delta": delta})


def test_fit_recovers_known_coefficients():
    q = pd.concat([chain("2026-10-05 10:15", 3000, seed=s, tier=s) for s in (0, 1, 2)])
    model, _ = spread.fit(q)
    for i, r in enumerate(model["bucket"]):
        assert np.isclose(r["a"], COEF[i][0], atol=5e-4)
        assert np.isclose(r["b"], COEF[i][1], atol=1e-4)
    assert [t["min_delta"] for t in model["tier"]] == [0.8, 0.9]
    for k, t in enumerate(model["tier"], 1):
        assert len(t["bucket"]) == 3
        for r in t["bucket"]:
            assert np.isclose(r["a"], TIER[k][0][0], atol=2e-3)
            assert np.isclose(r["b"], TIER[k][0][1], atol=1e-4)


def test_few_deep_quotes_pool_dte():
    q = pd.concat([chain("2026-10-05 10:15", 3000), chain("2026-10-05 10:15", 300, tier=1),
                   chain("2026-10-05 10:15", 3000, tier=2)])
    model, _ = spread.fit(q)
    assert len(model["bucket"]) == 3 and len(model["tier"][1]["bucket"]) == 3
    assert len(model["tier"][0]["bucket"]) == 1 and model["tier"][0]["bucket"][0]["n"] == 300


def test_filters_drop_after_hours_and_bad_quotes():
    day = chain("2026-10-05 10:15")
    late = chain("2026-10-05 16:29", seed=1)
    early = chain("2026-10-06 09:30", seed=2)
    no_iv = chain("2026-10-07 12:00", iv=np.nan, seed=3)
    bad = chain("2026-10-08 12:00", 3, seed=4).assign(bid=[0.0, 1.0, 1.0], ask=[1.0, 1.0, 0.5])
    no_delta = chain("2026-10-08 12:00", 2, seed=5).assign(delta=np.nan)
    deep = chain("2026-10-05 10:15", 3, seed=6).assign(delta=[0.95, -0.9, 0.8])
    q = spread.clean(pd.concat([day, late, early, no_iv, bad, no_delta, deep], ignore_index=True))
    assert len(q) == len(day) + 3
    assert list(q["tier"].iloc[-3:]) == [2, 1, 0]
    assert (q["asof"] == day["asof"].iloc[0]).all()


def test_half_spread_floor_and_buckets():
    model = {"floor": 0.005, "bucket": [{"max_dte": 14, "a": 0.0, "b": 0.01},
                                        {"max_dte": 30, "a": 0.0, "b": 0.02},
                                        {"max_dte": 60, "a": 0.0, "b": 0.03}]}
    out = spread.half_spread([0.1, 1.0, 1.0, 1.0, 1.0], [5, 14, 15, 31, 90], model)
    assert np.allclose(out, [0.005, 0.01, 0.02, 0.03, 0.03])


def test_tiers_used_only_with_delta():
    model = {"floor": 0.005, "bucket": [{"max_dte": 60, "a": 0.0, "b": 0.01}],
             "tier": [{"min_delta": 0.9, "bucket": [{"max_dte": 60, "a": 0.5, "b": 0.02}]},
                      {"min_delta": 0.8, "bucket": [{"max_dte": 60, "a": 0.1, "b": 0.0}]}]}
    mid, dte = [10.0] * 5, [20] * 5
    assert np.allclose(spread.half_spread(mid, dte, model), 0.1)
    out = spread.half_spread(mid, dte, model, delta=[0.5, -0.85, 0.9, -0.95, np.nan])
    assert np.allclose(out, [0.1, 0.1, 0.1, 0.7, 0.1])
    out = spread.half_spread(mid, dte, model, delta=[0.0, 0.85, 0.0, 0.0, 0.0])
    assert np.isclose(out[1], 0.1)


def test_old_model_files_still_work():
    old = {"floor": 0.005, "bucket": [{"max_dte": 60, "a": 0.0, "b": 0.01}]}
    assert np.allclose(spread.half_spread([10.0], [20], old, delta=[0.95]), 0.1)
    old |= {"deep_delta": 0.8, "deep_bucket": [{"max_dte": 60, "a": 0.5, "b": 0.02}]}
    assert np.allclose(spread.half_spread([10.0, 10.0], [20, 20], old, delta=[0.5, 0.85]),
                       [0.1, 0.7])


def test_save_load_roundtrip(tmp_path):
    model, _ = spread.fit(pd.concat([chain("2026-10-05 10:15", 1200),
                                     chain("2026-10-05 10:15", 50, tier=1),
                                     chain("2026-10-05 10:15", 900, tier=2)]))
    path = spread.save(model, tmp_path / "s.toml")
    back = spread.load(path)
    assert back["n_quotes"] == model["n_quotes"]
    assert np.isclose(back["bucket"][1]["b"], model["bucket"][1]["b"], atol=1e-6)
    assert [t["min_delta"] for t in back["tier"]] == [0.8, 0.9]
    assert [len(t["bucket"]) for t in back["tier"]] == [1, 3]
    assert back["tier"][1]["bucket"][2]["n"] == model["tier"][1]["bucket"][2]["n"]


def test_every_tier_fits_mean_cost():
    rng = np.random.default_rng(7)
    n = 3000
    wide = rng.random(n) < 0.4  # two clusters, like real deep ITM
    deep = chain("2026-10-05 10:15", n, seed=7, tier=2)
    half = np.where(wide, 1.5, 0.2) + rng.normal(0, 0.01, n)
    deep = deep.assign(bid=deep["mid"] - half, ask=deep["mid"] + half)
    normal = chain("2026-10-05 10:15", n)
    skew = rng.exponential(0.01, n)
    normal = normal.assign(bid=normal["bid"] - skew, ask=normal["ask"] + skew)
    model, q = spread.fit(pd.concat([normal, deep]))
    assert model["method"] == "ols" and [t["method"] for t in model["tier"]] == ["ols", "ols"]
    qual = spread.quality(model, q)
    for _, row in qual.loc[2].iterrows():
        assert np.isclose(row["mean_fitted"], row["mean_half"], rtol=0.02)
        assert row["mean_fitted"] > row["median_half"] + 0.3
    assert np.allclose(qual.loc[0, "mean_fitted"], qual.loc[0, "mean_half"], rtol=0.1)
