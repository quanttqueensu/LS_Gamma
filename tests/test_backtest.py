import copy
import shutil
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from lsgamma import experiments
from lsgamma.backtest import config, engine, metrics, report, run, sim
from lsgamma.pipeline import features, store
from lsgamma.trading import ledger, runner
from test_runner import FakeIB

SPOT = 600.0
DECISION = ["date", "ts", "expiry", "dte", "rv_forecast", "iv", "vrp", "signal"]
ACTIONS = ["date", "ts", "action", "side", "right", "strike", "expiry", "reason"]


class ByDay:
    vols = {}

    def fit(self, returns):
        self.last = returns.index.max()
        return self

    def predict(self, horizon):
        return ByDay.vols[self.last + pd.offsets.BDay(1)]


def chain(asof, mid=5.0, late=0, spot=SPOT):
    # late: dte labels understate expiry by weeks
    rows = []
    for k in range(1, 61 + 7 * late):
        e = asof.date() + timedelta(days=k)
        if e.weekday() != 4:
            continue
        for strike in (595.0, 600.0, 605.0):
            for right in ("C", "P"):
                rows.append({"asof": asof, "expiry": e, "dte": k - 7 * late,
                             "strike": strike, "right": right, "bid": mid - 0.1,
                             "ask": mid + 0.1, "mid": mid, "iv": 0.15,
                             "delta": 0.5 if right == "C" else -0.5, "gamma": 0.01,
                             "vega": 0.5, "theta": -0.1, "und_price": spot})
    return pd.DataFrame(rows)


def huge(c):
    return c.assign(mid=1e6, bid=0.0, ask=2e6, und_price=1e9)


def blank(c):
    return c.assign(mid=np.nan, bid=np.nan, ask=np.nan, und_price=np.nan)


def days(start, n):
    return [d.date() for d in pd.bdate_range(start, periods=n)]


def write(root, plan, times=("10:15",), make=chain, fill=None):
    for d, vol in plan:
        ByDay.vols[pd.Timestamp(d)] = vol
        for hhmm in times:
            asof = engine.at(d, hhmm)
            c = make(asof)
            store.save(c, "chain", asof, root)
            store.save(features.atm_iv(c), "atm_iv", asof, root)
            store.save(fill(c) if fill else c, "fill", asof, root)


@pytest.fixture
def bt(tmp_path, monkeypatch):
    monkeypatch.setitem(runner.FORECASTERS, "byday", ByDay)
    monkeypatch.setattr(experiments, "ROOT", tmp_path / "results")
    monkeypatch.setattr(ledger, "ROOT", tmp_path / "paper")
    cfg = config.load()
    cfg["signal"]["forecaster"] = "byday"
    root = tmp_path / "v1"
    root.mkdir()
    idx = pd.bdate_range("2018-01-01", "2024-12-31", name="date")
    rng = np.random.default_rng(0)
    pd.DataFrame({"ret": rng.normal(0, 0.01, len(idx))}, index=idx).to_parquet(
        root / "features.parquet")
    return cfg, root


def no_stops(cfg):
    cfg["exit"].update(short_stop_mult=1e12, long_stop_frac=1e12, short_profit_frac=0.0)
    return cfg


PARITY = [0.10, 0.12, 0.25, 0.16, 0.16, 0.16, 0.10, 0.16, 0.25, 0.16]


def live_and_engine(cfg, root, plan, monkeypatch):
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    feats = pd.read_parquet(root / "features.parquet")
    snap = lambda name, asof=None: (feats if name == "features"
                                    else pd.read_parquet(store.folder(asof, root) / f"{name}.parquet"))
    monkeypatch.setattr(runner.store, "load", snap)
    ib = FakeIB()
    for d, _ in plan:
        runner.run(ib, cfg, engine.at(d, "10:15"))
    live = ledger.read_log("signals")
    pd.testing.assert_frame_equal(out["signals"][DECISION], live[DECISION], check_dtype=False)
    lt = ledger.read_log("trades")
    pd.testing.assert_frame_equal(out["trades"][ACTIONS].fillna(""), lt[ACTIONS].fillna(""),
                                  check_dtype=False)
    assert out["hedges"]["shares"].tolist() == ledger.read_log("hedges")["shares"].tolist()
    return out, lt


def test_parity_with_live_runner(bt, monkeypatch):
    cfg, root = bt
    plan = list(zip(days("2024-03-04", len(PARITY)), PARITY))
    write(root, plan)
    out, lt = live_and_engine(cfg, root, plan, monkeypatch)
    assert lt["action"].tolist() == ["open", "close", "open", "close", "open", "close", "open"]
    assert lt["reason"].dropna().tolist() == ["flip", "flat", "flip"]


def spike_on(day):
    return lambda asof: chain(asof, mid=15.0 if asof.date() == day else 5.0)


def test_parity_with_stop_cooloff(bt, monkeypatch):
    cfg, root = bt
    cfg["exit"]["stop_cooloff_days"] = 2
    plan = list(zip(days("2024-03-04", 4), [0.10] * 4))
    write(root, plan, make=spike_on(plan[1][0]))
    out, lt = live_and_engine(cfg, root, plan, monkeypatch)
    assert lt["action"].tolist() == ["open", "close", "open"]
    assert lt["reason"].iloc[1] == "stop" and lt["date"].iloc[2] == str(plan[3][0])
    assert out["events"]["event"].tolist().count("cooloff") == 2


def test_stop_cooloff_hourly(bt):
    cfg, root = bt
    hourly = ["10:15", "11:15", "12:15"]
    cfg["schedule"] = {"signal": hourly, "hedge": hourly}
    d = days("2024-03-04", 2)
    make = lambda asof: chain(asof, mid=15.0 if asof == engine.at(d[0], "11:15") else 5.0)
    write(root, list(zip(d, [0.10, 0.10])), times=hourly, make=make)
    out = engine.backtest(cfg, d[0], d[1], root=root)
    t = out["trades"]
    assert t["action"].tolist() == ["open", "close", "open"]
    assert t["reason"].iloc[1] == "stop" and t["ts"].iloc[1].startswith(f"{d[0]}T11:15")
    assert t["ts"].iloc[2].startswith(f"{d[1]}T10:15")
    cool = out["events"][out["events"]["event"] == "cooloff"]
    assert cool["ts"].tolist() == [engine.at(d[0], h).isoformat(timespec="seconds")
                                   for h in ("11:15", "12:15")]


def test_garbage_fills_do_not_change_decisions(bt, tmp_path):
    cfg, root = bt
    cfg = no_stops(cfg)
    plan = list(zip(days("2024-03-04", len(PARITY)), PARITY))
    write(root, plan)
    good = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    bad_root = tmp_path / "bad"
    shutil.copytree(root, bad_root)
    write(bad_root, plan, fill=huge)
    bad = engine.backtest(cfg, plan[0][0], plan[-1][0], root=bad_root)
    pd.testing.assert_frame_equal(good["signals"], bad["signals"])
    cols = ["date", "ts", "action", "side", "strike", "expiry"]
    pd.testing.assert_frame_equal(good["trades"][cols], bad["trades"][cols])
    assert good["trades"]["reason"].fillna("").tolist() == bad["trades"]["reason"].fillna("").tolist()
    assert good["hedges"]["shares"].tolist() == bad["hedges"]["shares"].tolist()


def test_nan_fill_means_no_trade(bt):
    cfg, root = bt
    plan = list(zip(days("2024-03-04", 3), [0.10, 0.10, 0.25]))
    write(root, plan, fill=blank)
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    assert out["signals"]["signal"].tolist() == ["short", "short", "long"]
    assert out["trades"].empty and out["hedges"].empty
    assert (out["events"]["event"] == "no_fill").sum() == 3
    assert out["equity"]["equity"].eq(0).all()


def test_fill_view_read_after_decision(bt, monkeypatch):
    cfg, root = bt
    write(root, [(days("2024-03-04", 1)[0], 0.10)])
    seen = []
    real = engine.read
    monkeypatch.setattr(engine, "read", lambda f, n: seen.append(n) or real(f, n))
    engine.backtest(cfg, "2024-03-04", "2024-03-04", root=root)
    assert seen == ["chain", "atm_iv", "fill"]


def test_holdout_and_last_day_refused(bt):
    cfg, root = bt
    with pytest.raises(SystemExit, match="hold-out"):
        engine.backtest(cfg, "2024-12-01", "2025-01-02", root=root)
    with pytest.raises(SystemExit, match="last day"):
        engine.check_window(cfg, engine.day("2025-01-02"), engine.day("2026-08-03"), True)
    engine.check_window(cfg, engine.day("2025-01-02"), engine.day(cfg["history"]["last_day"]), True)
    with pytest.raises(SystemExit, match="first day"):
        engine.check_window(cfg, engine.day("2014-05-30"), engine.day("2015-01-02"), False)


@pytest.mark.parametrize("over,key", [('[backtest]\nholdout_start = "2027-01-01"\n', "holdout_start"),
                                      ('[backtest]\nfirst_day = "2010-01-04"\n', "first_day"),
                                      ('[history]\nlast_day = "2027-01-01"\n', "last_day"),
                                      ('[history]\ngrid = ["10:00"]\n', "grid")])
def test_experiment_cannot_move_pinned_keys(tmp_path, monkeypatch, over, key):
    (tmp_path / "x.toml").write_text(over)
    monkeypatch.setattr(experiments, "CONFIGS", tmp_path)
    with pytest.raises(SystemExit, match=key):
        config.load("x")


def test_experiment_may_pick_history_version(tmp_path, monkeypatch):
    (tmp_path / "x.toml").write_text('[history]\nversion = "v2"\n[backtest]\nstart = "2016-01-04"\n')
    monkeypatch.setattr(experiments, "CONFIGS", tmp_path)
    cfg = config.load("x")
    assert cfg["history"]["version"] == "v2" and cfg["backtest"]["start"] == "2016-01-04"


def test_embargo_blocks_late_entries(bt):
    cfg, root = bt
    plan = [(d, 0.10) for d in days("2024-11-18", 10)]
    write(root, plan)
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    assert set(out["signals"]["signal"]) == {"short"}
    assert out["trades"].empty


def test_embargo_force_closes_at_boundary(bt):
    cfg, root = bt
    plan = [(d, 0.10) for d in pd.bdate_range("2024-11-11", "2024-12-31").date]
    write(root, plan, make=lambda asof: chain(asof, late=8))
    out = engine.backtest(cfg, "2024-11-11", "2024-12-31", root=root)
    t = out["trades"]
    assert t["action"].tolist() == ["open", "close"]
    assert t["date"].tolist() == ["2024-11-11", "2024-12-31"]
    assert t["reason"].iloc[-1] == "embargo"


def test_missing_snapshot_skipped_no_fallback(bt):
    cfg, root = bt
    plan = list(zip(days("2024-03-04", 3), [0.10, 0.10, 0.10]))
    write(root, plan)
    shutil.rmtree(root / str(plan[1][0]))
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    assert out["signals"]["date"].tolist() == [str(plan[0][0]), str(plan[2][0])]
    assert str(plan[1][0]) not in set(out["equity"]["date"])
    skipped = out["events"][out["events"]["event"] == "skipped"]
    assert skipped["date"].tolist() == [str(plan[1][0])]
    m = metrics.summary(out, cfg)
    assert m["skipped"] == 1 and m["skipped_share"] == pytest.approx(1 / 3)


def test_flat_exit_counts_days_hourly(bt):
    cfg, root = bt
    hourly = cfg["history"]["grid"][:4]
    cfg["schedule"] = {"signal": hourly, "hedge": hourly}
    plan = list(zip(days("2024-03-04", 5), [0.10, 0.16, 0.16, 0.16, 0.16]))
    write(root, plan, times=hourly)
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    t = out["trades"]
    assert t["action"].tolist() == ["open", "close"]
    assert t["reason"].iloc[-1] == "flat"
    assert t["ts"].iloc[-1] == engine.at(plan[3][0], "10:15").isoformat(timespec="seconds")


def test_stop_checked_at_hedge_only_time(bt):
    cfg, root = bt
    cfg["schedule"] = {"signal": ["10:15"], "hedge": ["10:15", "12:15"]}
    d = days("2024-03-04", 1)[0]
    make = lambda asof: chain(asof, mid=15.0 if f"{asof:%H%M}" == "1215" else 5.0)
    write(root, [(d, 0.10)], times=("10:15", "12:15"), make=make)
    out = engine.backtest(cfg, d, d, root=root)
    t = out["trades"]
    assert t["action"].tolist() == ["open", "close"]
    assert t["reason"].iloc[-1] == "stop"
    assert t["ts"].iloc[-1].startswith(f"{d}T12:15")
    fees = out["trades"]["commission"].sum() + out["hedges"]["commission"].iloc[0]
    assert t["pnl_net"].iloc[-1] == pytest.approx(t["pnl"].iloc[-1] - fees)


def unmarked(asof):
    # 12:15 drops the held 600 put, spot 580
    if f"{asof:%H%M}" != "1215":
        return chain(asof)
    c = chain(asof, spot=580.0)
    return c[~((c["strike"] == 600.0) & (c["right"] == "P"))]


def test_missing_mark_uses_conservative_mark(bt, tmp_path):
    cfg, root = bt
    cfg["schedule"] = {"signal": ["10:15"], "hedge": ["10:15", "12:15"]}
    d = days("2024-03-04", 1)[0]
    full = lambda c: chain(c["asof"].iloc[0], spot=float(c["und_price"].iloc[0]))
    write(root, [(d, 0.10)], times=("10:15", "12:15"), make=unmarked, fill=full)
    out = engine.backtest(cfg, d, d, root=root)
    assert "no_mark" in set(out["events"]["event"])
    assert out["trades"]["reason"].iloc[-1] == "stop"

    held = engine.backtest(no_stops(cfg), d, d, root=root)
    assert held["trades"]["action"].tolist() == ["open"]
    assert held["equity"]["option"].iloc[-1] == pytest.approx(-20.0 * 100)


def test_conservative_mark_rule():
    short = {"side": "short", "right": "P", "strike": 600.0}
    long_ = {"side": "long", "right": "C", "strike": 600.0}
    assert sim.conservative(short, 5.0, 580.0) == 20.0
    assert sim.conservative(short, 5.0, 610.0) == 5.0
    assert sim.conservative(long_, 5.0, 610.0) == 5.0
    assert sim.conservative(long_, 5.0, 590.0) == 0.0
    assert sim.conservative(short, float("nan"), 590.0) == 10.0


def test_flip_carries_hedge_shares(bt, monkeypatch):
    cfg, root = bt
    plan = list(zip(days("2024-03-04", 2), [0.10, 0.25]))
    write(root, plan)
    opened = []
    real = sim.open_option
    monkeypatch.setattr(sim, "open_option", lambda b, pos, cost: opened.append(pos) or real(b, pos, cost))
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    assert out["trades"]["action"].tolist() == ["open", "close", "open"]
    assert opened[1]["side"] == "long"
    assert opened[1]["hedges"][0] == {"date": str(plan[1][0]), "ts": opened[1]["entry_ts"],
                                      "shares": -50, "price": SPOT}
    assert out["hedges"]["shares"].tolist() == [-50]


@pytest.mark.parametrize("fill_spot,price,src", [(585.0, 15.0, "fill"), (np.nan, 10.0, "decide")])
def test_expired_settles_on_expiry_day_spot(bt, fill_spot, price, src):
    cfg, root = bt
    cfg["exit"]["exit_dte"] = -1
    plan = [(d, 0.10) for d in pd.bdate_range("2024-03-04", "2024-04-08").date]
    write(root, plan)
    late = engine.at(engine.day("2024-04-05"), "15:45")
    store.save(chain(late, spot=590.0), "chain", late, root)
    store.save(chain(late, spot=fill_spot), "fill", late, root)
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    t = out["trades"]
    assert t["expiry"].iloc[0] == "2024-04-05"
    c = t[t["action"] == "close"].iloc[0]
    assert c["reason"] == "expired" and c["date"] == "2024-04-08"
    assert c["price"] == pytest.approx(price) and c["commission"] == 0.0
    ev = out["events"][out["events"]["event"] == "expired"]
    assert f"{src} 2024-04-05T15:45" in ev["detail"].iloc[0]


def test_commissions_and_spread_applied(bt):
    cfg, root = bt
    d = days("2024-03-04", 1)[0]
    write(root, [(d, 0.10)])
    out = engine.backtest(cfg, d, d, root=root)
    t, h, eq = out["trades"].iloc[0], out["hedges"].iloc[0], out["equity"].iloc[-1]
    assert t["price"] == pytest.approx(4.9)
    assert h["shares"] == -50 and h["price"] == pytest.approx(SPOT - 0.005)
    # $1 minimum per order
    assert t["commission"] == pytest.approx(1.0) and h["commission"] == pytest.approx(1.0)
    # credit 490 vs mark 500, hedge 0.25 off spot, fees
    assert eq["equity"] == pytest.approx(-10 - 0.25 - 2.0)

    cfg["backtest"]["min_per_order"] = 0.0
    out = engine.backtest(cfg, d, d, root=root)
    assert out["trades"]["commission"].iloc[0] == pytest.approx(0.65)
    assert out["hedges"]["commission"].iloc[0] == pytest.approx(0.25)

    cfg["backtest"]["spread_mult"] = 2.0
    out = engine.backtest(cfg, d, d, root=root)
    assert out["trades"]["price"].iloc[0] == pytest.approx(4.8)
    assert out["hedges"]["price"].iloc[0] == pytest.approx(SPOT - 0.01)


def test_registry_row_per_run(bt):
    cfg, root = bt
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])))
    (root / "manifest.json").write_text(
        '{"config_hash": "abc", "builds": [{"features_end": "2024-12-31"}]}')
    for mult in (1.0, 2.0):
        run.trial("demo", cfg, d[0], d[1], mult=mult, root=root)
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    assert reg["spread_mult"].tolist() == [1.0, 2.0]
    assert not reg["holdout"].any()
    assert {"experiment", "run", "commit", "version", "start", "end", "schedule",
            "pnl", "sharpe", "max_dd", "es_5", "trades", "win_rate", "decide_smile",
            "skipped", "no_fill", "no_delta", "no_mark", "no_fill_share"} <= set(reg.columns)
    assert (experiments.ROOT / reg["run"].iloc[0] / "signals.parquet").exists()
    assert reg["config_hash"].tolist() == ["abc", "abc"]
    assert reg["features_end"].iloc[0] == "2024-12-31"
    assert reg["last_day_used"].iloc[0] == str(d[1])
    assert len(experiments.trials("demo")) == 2


def test_config_merges_experiment_over_base(tmp_path, monkeypatch):
    (tmp_path / "x.toml").write_text('[signal]\nshort_band = 0.03\n[backtest]\nspread_mult = 1.5\n')
    monkeypatch.setattr(experiments, "CONFIGS", tmp_path)
    cfg = config.load("x")
    assert cfg["signal"]["short_band"] == 0.03 and cfg["signal"]["long_band"] == -0.05
    assert cfg["backtest"]["spread_mult"] == 1.5 and cfg["backtest"]["commission_share"] == 0.005
    assert cfg["history"]["grid"][0] == "10:15"


def test_metrics_on_simple_equity():
    eq = pd.DataFrame({"date": ["d1", "d1", "d2", "d3"], "equity": [5.0, 10.0, 4.0, 12.0]})
    daily = metrics.daily_pnl(eq)
    assert daily.tolist() == [10.0, -6.0, 8.0]
    assert metrics.max_drawdown(daily) == 6.0
    assert metrics.expected_shortfall(daily) == -6.0


def test_decide_smile_share():
    t = pd.DataFrame({"action": ["open", "close", "open", "close"],
                      "src": ["fill_smile", "decide_smile", "decide_smile", "expiry"]})
    assert metrics.decide_smile_share(t) == pytest.approx(2 / 3)
    assert metrics.decide_smile_share(t.drop(columns="src")) == 0.0


def test_forecast_window_matches_live(bt):
    cfg, root = bt
    feats = pd.read_parquet(root / "features.parquet")
    asof = engine.at(engine.day("2024-03-04"), "10:15")
    used = runner.completed(engine.window(feats, asof, 5), asof)
    assert used.index.min() == pd.Timestamp("2019-03-04")
    assert used.index.max() < pd.Timestamp("2024-03-04")


def reset_run(cfg, root, vols):
    cfg["exit"]["stop_cooloff_days"] = 0
    cfg["backtest"]["stop_reset"] = True
    plan = list(zip(days("2024-03-04", len(vols)), vols))
    write(root, plan, make=spike_on(plan[1][0]))
    return plan, engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)


def test_stop_reset_waits_while_signal_stays(bt):
    cfg, root = bt
    plan, out = reset_run(cfg, root, [0.10] * 4)
    assert out["trades"]["action"].tolist() == ["open", "close"]
    assert out["trades"]["reason"].iloc[1] == "stop"
    assert out["events"]["event"].tolist().count("reset_wait") == 3


def test_stop_reset_reenters_after_flat(bt):
    cfg, root = bt
    plan, out = reset_run(cfg, root, [0.10, 0.10, 0.16, 0.10])
    t = out["trades"]
    assert t["action"].tolist() == ["open", "close", "open"]
    assert t["date"].iloc[2] == str(plan[3][0])


def test_stop_reset_off_by_default(bt):
    cfg, root = bt
    assert cfg["backtest"]["stop_reset"] is False
    assert "stop_reset" not in config.read(config.CONFIGS / "paper.toml")["exit"]


def test_variants_run_each_at_both_mults(bt):
    cfg, root = bt
    d = days("2024-03-04", 3)
    write(root, list(zip(d, [0.10] * 3)))
    cfg["backtest"].update(start=str(d[0]), end=str(d[-1]))
    out = run.variants("demo", cfg, {"a": {}, "b": {"hedge": {"min_shares": 1000}}}, root=root)
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    assert reg["experiment"].tolist() == ["demo/a"] * 2 + ["demo/b"] * 2
    assert reg["spread_mult"].tolist() == [1.0, 2.0, 1.0, 2.0]
    assert not reg["holdout"].any()
    hedged = [pd.read_parquet(experiments.ROOT / r / "hedges.parquet") for r in reg["run"]]
    assert len(hedged[0]) > 0 and len(hedged[2]) == 0
    assert set(out) == {"a", "b"}


def test_variants_cannot_move_pinned_keys(bt):
    cfg, root = bt
    with pytest.raises(SystemExit, match="holdout_start"):
        run.variants("demo", cfg, {"x": {"backtest": {"holdout_start": "2030-01-01"}}}, root=root)


def test_registry_lock_keeps_parallel_rows(bt):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(lambda i: run.register({"experiment": f"e{i}", "pnl": float(i)}), range(16)))
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    assert sorted(reg["experiment"]) == sorted(f"e{i}" for i in range(16))


def test_report_tables_and_charts(bt, tmp_path):
    from lsgamma.backtest import report
    cfg, root = bt
    plan = list(zip(days("2019-12-23", len(PARITY)), PARITY))
    write(root, plan)
    cfg["backtest"].update(start=str(plan[0][0]), end=str(plan[-1][0]))
    run.variants("demo", cfg, {"a": {}}, root=root)
    sets = {"baseline": report.runs("demo/a"), "a": report.runs("demo/a")}
    assert set(sets["a"]) == {1.0, 2.0} and report.trials("demo") == 2
    t = report.table(sets)
    whole = t[(t["period"] == "all") & (t["mult"] == 1.0)].iloc[0]
    halves = t[(t["period"] != "all") & (t["mult"] == 1.0) & (t["label"] == "a")]
    assert np.isclose(halves["pnl"].sum(), whole["pnl"])
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    assert np.isclose(whole["pnl"], reg["pnl"].iloc[0])
    for path in report.standard(sets, tmp_path / "figs"):
        assert path.exists() and path.stat().st_size > 0


def test_baseline_matches_config_and_takes_first(bt):
    from lsgamma.backtest import report
    cfg, root = bt
    d = days("2024-03-04", 3)
    write(root, list(zip(d, [0.10] * 3)))
    for _ in range(2):
        for mult in (1.0, 2.0):
            run.trial("baseline", cfg, d[0], d[-1], mult=mult, root=root)
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    first = report.baseline(cfg)
    assert sorted(first) == [1.0, 2.0] and not report.stale(cfg)
    assert first[1.0]["equity"].equals(report.load(reg["run"].iloc[0])["equity"])
    changed = copy.deepcopy(cfg)
    changed["hedge"]["min_shares"] = 10
    assert report.stale(changed) and report.stale(cfg, holdout=True)


def test_new_flag_off_keeps_baseline_current(bt):
    from lsgamma.backtest import report
    cfg, root = bt
    saved = copy.deepcopy(cfg)
    del saved["backtest"]["stop_reset"]
    assert report.same(saved, cfg)
    cfg["backtest"]["stop_reset"] = True
    assert not report.same(saved, cfg)


def holdout_setup(cfg, root):
    cfg["backtest"]["holdout_start"] = "2024-03-04"
    cfg["history"]["last_day"] = "2024-03-15"
    write(root, list(zip(days("2024-03-04", 10), PARITY)))
    return {**cfg, "variants": {"a": {"hedge": {"min_shares": 5}}}}


def test_holdout_runs_once_with_baseline(bt):
    cfg, root = bt
    exp = holdout_setup(cfg, root)
    out = run.holdout("demo", "a", exp, cfg, root=root)
    assert set(out) == {"a", "baseline"}
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    assert reg["holdout"].all() and len(reg) == 4
    assert reg["experiment"].tolist() == ["demo/a"] * 2 + ["baseline"] * 2
    assert set(reg["start"]) == {"2024-03-04"} and set(reg["end"]) == {"2024-03-15"}
    with pytest.raises(SystemExit, match="already has a hold-out run"):
        run.holdout("demo", "a", exp, cfg, root=root)


def test_holdout_reuses_existing_baseline(bt):
    cfg, root = bt
    exp = holdout_setup(cfg, root)
    run.holdout("demo", "a", exp, cfg, root=root)
    exp["variants"]["b"] = {"hedge": {"min_shares": 20}}
    out = run.holdout("demo", "b", exp, cfg, root=root)
    assert set(out) == {"b"}
    reg = pd.read_parquet(experiments.ROOT / "registry.parquet")
    assert (reg["experiment"] == "baseline").sum() == 2


def ladder(cfg, root, vols, n=3):
    cfg = no_stops(cfg)
    cfg["backtest"]["max_positions"] = n
    plan = list(zip(days("2024-03-04", len(vols)), vols))
    write(root, plan)
    return plan, engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)


def test_max_positions_ladders_one_per_run(bt):
    cfg, root = bt
    plan, out = ladder(cfg, root, [0.10] * 5)
    t = out["trades"]
    assert t["action"].tolist() == ["open"] * 3
    assert t["date"].tolist() == [str(d) for d, _ in plan[:3]]
    assert out["hedges"]["shares"].tolist() == [-50, -50, -50]
    assert out["equity"]["shares"].iloc[-1] == -150


def test_max_positions_flip_closes_all(bt):
    cfg, root = bt
    plan, out = ladder(cfg, root, [0.10, 0.10, 0.25])
    t = out["trades"]
    assert t["action"].tolist() == ["open", "open", "close", "close", "open"]
    assert t["reason"].dropna().tolist() == ["flip", "flip"]
    assert t["side"].iloc[-1] == "long"
    assert out["hedges"]["shares"].tolist() == [-50, -50, 50]
    rt = report.round_trips(out)
    assert rt["entry_date"].tolist() == [str(plan[0][0]), str(plan[1][0])]


def test_max_positions_fees_add_up(bt):
    cfg, root = bt
    plan, out = ladder(cfg, root, [0.10, 0.10, 0.10, 0.16, 0.16, 0.16, 0.16])
    t, h = out["trades"], out["hedges"]
    closes = t[t["action"] == "close"]
    assert len(closes) == 3 and set(closes["reason"]) == {"flat"}
    eq = out["equity"]["equity"].iloc[-1]
    unwind = abs(h["shares"].iloc[-1]) * cfg["backtest"]["share_half_spread"]
    fees = t["commission"].sum() + h["commission"].sum()
    assert np.isclose(eq, closes["pnl"].sum() - fees - unwind)
    assert np.isclose(closes["pnl"].sum() - closes["pnl_net"].sum(), fees - h["commission"].iloc[-1])
    assert out["equity"]["shares"].iloc[-1] == 0


def test_pairs_match_by_entry_time():
    t = pd.DataFrame({"action": ["open", "open", "close", "close"],
                      "ts": ["a", "b", "c", "d"], "date": ["2024-01-01", "2024-01-02",
                                                          "2024-01-05", "2024-01-09"],
                      "entry_ts": ["a", "b", "b", "a"]})
    o, c = metrics.pairs(t)
    assert o["ts"].tolist() == ["b", "a"]
    assert metrics.holding_days(t) == (3 + 8) / 2


def gate_run(cfg, root, vol, prev, today, n=1):
    plan = list(zip(days("2024-03-04", n), [vol] * n))
    write(root, plan)
    path = root / "features.parquet"
    f = pd.read_parquet(path)
    f["vix_vix3m"] = 0.9
    f.loc[pd.Timestamp("2024-03-01"), "vix_vix3m"] = prev
    f.loc[pd.Timestamp(plan[0][0]), "vix_vix3m"] = today
    f.to_parquet(path)
    return plan, engine.backtest(no_stops(cfg), plan[0][0], plan[-1][0], root=root)


@pytest.mark.parametrize("vol, prev, opens", [(0.10, 1.05, False), (0.10, 1.0, False),
                                               (0.10, 0.99, True), (0.10, np.nan, True),
                                               (0.25, 1.05, True)])
def test_short_gate_blocks_on_yesterday_ratio(bt, vol, prev, opens):
    cfg, root = bt
    cfg["backtest"]["short_gate"] = 1.0
    plan, out = gate_run(cfg, root, vol, prev, today=0.9)
    assert (len(out["trades"]) == 1) is opens
    gates = out["events"][out["events"]["event"] == "gate"] if len(out["events"]) else []
    assert len(gates) == (0 if opens else 1)
    if not opens:
        assert gates["detail"].iloc[0] == f"no short entry, VIX/VIX3M {prev:.3f}"


def test_short_gate_ignores_today(bt):
    cfg, root = bt
    cfg["backtest"]["short_gate"] = 1.0
    plan, out = gate_run(cfg, root, 0.10, prev=0.9, today=5.0)
    assert out["trades"]["action"].tolist() == ["open"]


def test_short_gate_waits_then_enters(bt):
    cfg, root = bt
    cfg["backtest"]["short_gate"] = 1.0
    plan, out = gate_run(cfg, root, 0.10, prev=1.2, today=0.9, n=2)
    assert out["trades"]["date"].tolist() == [str(plan[1][0])]


def test_short_gate_off_by_default(bt):
    cfg, root = bt
    assert cfg["backtest"]["short_gate"] == 0.0
    assert "short_gate" not in config.read(config.CONFIGS / "paper.toml")["exit"]
    plan = list(zip(days("2024-03-04", len(PARITY)), PARITY))
    write(root, plan)
    plain = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    path = root / "features.parquet"
    pd.read_parquet(path).assign(vix_vix3m=5.0).to_parquet(path)
    out = engine.backtest(cfg, plan[0][0], plan[-1][0], root=root)
    for k in engine.OUTPUTS:
        pd.testing.assert_frame_equal(out[k], plain[k])


def skewed(asof):
    c = chain(asof)
    put = c["right"] == "P"
    return c.assign(delta=np.where(put, c["strike"].map({595.0: -0.25, 600.0: -0.5, 605.0: -0.7}),
                                   c["delta"]))


def test_put_delta_picks_otm_strike(bt):
    cfg, root = bt
    cfg["backtest"]["put_delta"] = 0.25
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])), make=skewed)
    out = engine.backtest(cfg, d[0], d[-1], root=root)
    t = out["trades"]
    assert t["action"].iloc[0] == "open" and t["right"].iloc[0] == "P"
    assert t["strike"].iloc[0] == 595.0
    assert out["hedges"]["shares"].iloc[0] == -25


def test_put_delta_off_keeps_atm(bt):
    cfg, root = bt
    assert cfg["backtest"]["put_delta"] == 0.0
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])), make=skewed)
    t = engine.backtest(cfg, d[0], d[-1], root=root)["trades"]
    assert t["strike"].iloc[0] == 600.0


def test_put_delta_leaves_long_calls(bt):
    cfg, root = bt
    cfg["backtest"]["put_delta"] = 0.25
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.25, 0.25])), make=skewed)
    t = engine.backtest(cfg, d[0], d[-1], root=root)["trades"]
    assert t["right"].iloc[0] == "C" and t["strike"].iloc[0] == 600.0


def stressed(cfg, budget=0.35):
    cfg["backtest"].update(stress_budget=budget, stress_drop=0.2, stress_vol=0.6)
    return cfg


def test_stress_budget_sizes_hedged_short_put(bt):
    cfg, root = bt
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])))
    out = engine.backtest(stressed(cfg), d[0], d[-1], root=root)
    # crash put about 124.8: 14 x 5,981 + 1 x 120 <= 87,500
    assert out["trades"]["qty"].iloc[0] == 14
    assert out["hedges"]["shares"].iloc[0] == -700


def test_stress_budget_unhedged_counts_whole_delta(bt):
    cfg, root = bt
    cfg["hedge"]["min_shares"] = 1e9
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])))
    out = engine.backtest(stressed(cfg), d[0], d[-1], root=root)
    assert out["trades"]["qty"].iloc[0] == 7 and out["hedges"].empty


def test_stress_budget_counts_band_gap(bt):
    cfg, root = bt
    cfg["backtest"]["ww_band"] = 30.0
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])))
    out = engine.backtest(stressed(cfg), d[0], d[-1], root=root)
    # band 30 x sqrt(12) shares stays unhedged
    assert out["trades"]["qty"].iloc[0] == 12


def test_stress_budget_leaves_long_calls(bt):
    cfg, root = bt
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.25, 0.25])))
    t = engine.backtest(stressed(cfg), d[0], d[-1], root=root)["trades"]
    assert t["right"].iloc[0] == "C" and t["qty"].iloc[0] == 1


def test_stress_budget_below_one_contract_skips_entry(bt):
    cfg, root = bt
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])))
    out = engine.backtest(stressed(cfg, budget=0.01), d[0], d[-1], root=root)
    assert out["trades"].empty
    assert "stress budget below one contract" in out["events"]["detail"].tolist()


def drifting(deltas):
    def make(asof):
        c = chain(asof)
        return c.assign(delta=np.where(c["right"] == "P", -deltas[asof.date()], c["delta"]))
    return make


@pytest.mark.parametrize("k, shares", [(0.0, [-50, -25, -10]), (30.0, [-50, -35])])
def test_ww_band_scales_with_gamma(bt, k, shares):
    cfg, root = bt
    cfg["backtest"]["ww_band"] = k  # gamma 1 share per $: band 30
    d = days("2024-03-04", 3)
    write(root, list(zip(d, [0.10] * 3)), make=drifting(dict(zip(d, [0.5, 0.75, 0.85]))))
    assert engine.backtest(cfg, d[0], d[-1], root=root)["hedges"]["shares"].tolist() == shares


def test_stress_and_band_off_by_default(bt):
    cfg, root = bt
    flags = ("stress_budget", "stress_drop", "stress_vol", "ww_band")
    assert all(cfg["backtest"][k] == 0.0 for k in flags)
    paper = config.read(config.CONFIGS / "paper.toml")
    assert not any(k in paper[s] for k in flags for s in ("size", "hedge"))
    saved = copy.deepcopy(cfg)
    for k in flags:
        del saved["backtest"][k]
    assert report.same(saved, cfg)
    d = days("2024-03-04", 2)
    write(root, list(zip(d, [0.10, 0.10])))
    assert engine.backtest(cfg, d[0], d[-1], root=root)["trades"]["qty"].iloc[0] == 1
