import argparse
import json
import math
from concurrent.futures import ProcessPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma import experiments
from lsgamma.backtest import config, engine, report, run
from lsgamma.history import marks
from lsgamma.pipeline import store
from lsgamma.trading import runner, selection

NAME = "2026-11-05-ltr-puts"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
WORK = experiments.ROOT / NAME / "ranker"  # labels, features, picks (not committed)
REF = "2026-10-22-stress-sized-puts/hedged"  # reused, not rerun
MULTS = (1.0, 2.0)
LIMIT = 87500.0  # 35% stress budget of $250k
DELTAS = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.45)  # paper eq. 1
SKIP = 0.0  # pick value for no trade
YEARS = range(2017, 2025)  # walk-forward test years
HOLDOUT = ("2025-01-01", "2026-07-11")  # one window, hold-out mode only
GATE, EARLY = pd.DateOffset(months=6), pd.DateOffset(months=3)
GAINS = [0, 1, 3, 7, 15]  # paper eq. 9
CUTS = [10, 40, 60, 90]  # paper eq. 7
HOLD = 50  # calendar days a label run may last
WORKERS = 12
PARAMS = {"objective": "lambdarank", "label_gain": GAINS, "num_leaves": 16,
          "learning_rate": 0.05, "min_child_samples": 100, "subsample": 0.8,
          "subsample_freq": 1, "colsample_bytree": 0.8, "reg_alpha": 0.1, "reg_lambda": 1.0,
          "n_estimators": 2000, "num_threads": 1, "deterministic": True, "random_state": 0,
          "verbose": -1}
LAST = ["vix", "vix_pct_1y", "vix_vix3m", "vix9d_vix", "vvix", "rv_d", "rv_w", "rv_m",
        "above_ma50", "above_ma200", "ret"]  # prior close
DAY = LAST + ["ret_5", "ret_20", "dvix_5", "atm_iv", "rv_fc", "vrp", "dte", "term_slope",
              "skew_25", "wing_10", "weekday", "days_fomc", "days_cpi"]
CAND = ["delta", "is_skip", "abs_delta", "iv_k", "iv_rel", "moneyness", "premium", "rel_spread",
        "qty", "credit_budget", "vega_budget", "theta_budget", "gamma_budget"]
FEATS = DAY + CAND
VARIANTS = ("ltr", "ltr_nogate", "ltr_noskip")
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
    "above": lambda v, r, x: v > x,  # absolute
    "at_most": lambda v, r, x: v <= x,  # absolute
}

# scheduled FOMC statements (federalreserve.gov), 2014-06 to 2024
FOMC = """2014-06-18 2014-07-30 2014-09-17 2014-10-29 2014-12-17
2015-01-28 2015-03-18 2015-04-29 2015-06-17 2015-07-29 2015-09-17 2015-10-28 2015-12-16
2016-01-27 2016-03-16 2016-04-27 2016-06-15 2016-07-27 2016-09-21 2016-11-02 2016-12-14
2017-02-01 2017-03-15 2017-05-03 2017-06-14 2017-07-26 2017-09-20 2017-11-01 2017-12-13
2018-01-31 2018-03-21 2018-05-02 2018-06-13 2018-08-01 2018-09-26 2018-11-08 2018-12-19
2019-01-30 2019-03-20 2019-05-01 2019-06-19 2019-07-31 2019-09-18 2019-10-30 2019-12-11
2020-01-29 2020-04-29 2020-06-10 2020-07-29 2020-09-16 2020-11-05 2020-12-16
2021-01-27 2021-03-17 2021-04-28 2021-06-16 2021-07-28 2021-09-22 2021-11-03 2021-12-15
2022-01-26 2022-03-16 2022-05-04 2022-06-15 2022-07-27 2022-09-21 2022-11-02 2022-12-14
2023-02-01 2023-03-22 2023-05-03 2023-06-14 2023-07-26 2023-09-20 2023-11-01 2023-12-13
2024-01-31 2024-03-20 2024-05-01 2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18"""
# CPI release dates (bls.gov archive), MMDDYYYY
CPI = """06172014 07222014 08192014 09172014 10222014 11202014 12172014
01162015 02262015 03242015 04172015 05222015 06182015 07172015 08192015 09162015 10152015 11172015 12152015
01202016 02192016 03162016 04142016 05172016 06162016 07152016 08162016 09162016 10182016 11172016 12152016
01182017 02152017 03152017 04142017 05122017 06142017 07142017 08112017 09142017 10132017 11152017 12132017
01122018 02142018 03132018 04112018 05102018 06122018 07122018 08102018 09132018 10112018 11142018 12122018
01112019 02132019 03122019 04102019 05102019 06122019 07112019 08132019 09122019 10102019 11132019 12112019
01142020 02132020 03112020 04102020 05122020 06102020 07142020 08122020 09112020 10132020 11122020 12102020
01132021 02102021 03102021 04132021 05122021 06102021 07132021 08112021 09142021 10132021 11102021 12102021
01122022 02102022 03102022 04122022 05112022 06102022 07132022 08102022 09132022 10132022 11102022 12132022
01122023 02142023 03142023 04122023 05102023 06132023 07122023 08102023 09132023 10122023 11142023 12122023
01112024 02132024 03122024 04102024 05152024 06122024 07112024 08142024 09112024 10102024 11132024 12112024"""
FOMC_D = [date.fromisoformat(d) for d in FOMC.split()]
CPI_D = [date(int(c[4:]), int(c[:2]), int(c[2:4])) for c in CPI.split()]


# ---- book, labels and features ----

def book(cfg, k=None):
    # the trial book without picks
    b = config.merge({x: v for x, v in cfg.items() if x != "variants"}, cfg["variants"]["ltr"])
    return config.merge(b, {"backtest": {"put_picks": "", **({"put_delta": k} if k else {})}})


def label(b, d, end, cache):
    # first round trip opened on d
    out = engine.backtest(b, d, min(d + timedelta(days=HOLD), end), cache=cache)
    t = out["trades"]
    if t.empty or t["action"].iloc[0] != "open" or t["date"].iloc[0] != str(d):
        return None
    shut = t[t["action"] == "close"]
    if shut.empty:
        return None
    c, eq = shut.iloc[0], out["equity"]
    path = eq[(eq["date"] >= str(d)) & (eq["date"] < c["date"])]["equity"].to_numpy()
    bars = np.diff(np.r_[0.0, path, c["pnl_net"]])  # daily marks, paper eq. 5
    tdd = math.sqrt(float((np.minimum(bars, 0) ** 2).sum()))
    return {"close": c["date"], "contracts": int(t["qty"].iloc[0]), "pnl": float(c["pnl_net"]),
            "reason": c["reason"], "bars": len(bars), "score": float(c["pnl_net"]) / (tdd + 1e-8)}


def nearest(rows, k):
    return rows.loc[(rows["delta"].abs() - k).abs().idxmin()]


def ahead(d, dates):
    gaps = [(e - d).days for e in dates if e >= d]
    return gaps[0] if gaps else np.nan


def day_feats(feats, d, dec, chain, atm):
    f = runner.completed(feats, engine.at(d, "10:15"))
    last, exp = f.iloc[-1], selection.to_date(dec["expiry"])
    puts = chain[(chain["expiry"] == exp) & (chain["right"] == "P")].dropna(
        subset=["mid", "delta", "iv"])
    iv25, iv10 = (float(nearest(puts, k)["iv"]) for k in (0.25, 0.10))
    near = atm.dropna(subset=["atm_iv"]).sort_values("dte")
    near = near[near["dte"] >= 5]
    return {**{c: float(last[c]) for c in LAST},
            "ret_5": float(f["ret"].iloc[-5:].sum()), "ret_20": float(f["ret"].iloc[-20:].sum()),
            "dvix_5": float(last["vix"] - f["vix"].iloc[-6]), "atm_iv": dec["iv"],
            "rv_fc": dec["rv_forecast"], "vrp": dec["vrp"], "dte": dec["dte"],
            "term_slope": dec["iv"] - float(near["atm_iv"].iloc[0]) if len(near) else np.nan,
            "skew_25": iv25 - dec["iv"], "wing_10": iv10 - iv25, "weekday": d.weekday(),
            "days_fomc": ahead(d, FOMC_D), "days_cpi": ahead(d, CPI_D)}


def cand_feats(b, d, dec, chain):
    # each delta as the engine would open it
    exp, spot = selection.to_date(dec["expiry"]), runner.spot(chain)
    puts = chain[(chain["expiry"] == exp) & (chain["right"] == "P")].dropna(subset=["mid", "delta"])
    budget = b["backtest"]["stress_budget"] * b["size"]["capital"]
    years = float(marks.years(engine.at(d, "10:15"), [exp])[0])
    rows = []
    for k in DELTAS:
        r = nearest(puts, k)
        q, mid = engine.stress_qty(b, r, spot, years, budget), float(r["mid"])
        rows.append({"delta": k, "is_skip": 0, "abs_delta": abs(float(r["delta"])),
                     "iv_k": float(r["iv"]), "iv_rel": float(r["iv"]) - dec["iv"],
                     "moneyness": math.log(float(r["strike"]) / spot), "premium": mid / spot,
                     "rel_spread": float(r["ask"] - r["bid"]) / mid if mid > 0 else np.nan, "qty": q,
                     "credit_budget": q * mid * 100 / budget,
                     "vega_budget": q * float(r["vega"]) * 100 / budget,
                     "theta_budget": q * float(r["theta"]) * 100 / budget,
                     "gamma_budget": q * abs(float(r["gamma"])) * spot ** 2 / budget})
    return rows + [{"delta": SKIP, "is_skip": 1}]


def day_rows(b, feats, root, d, rv_for):
    # 10:15 decide view, as the engine sees it
    asof = engine.at(d, "10:15")
    folder = store.folder(asof, root)
    chain, atm = engine.read(folder, "chain"), engine.read(folder, "atm_iv")
    if chain is None or atm is None:
        return []
    try:
        runner.check(chain)
        dec = runner.decide(feats, chain, atm, b, asof, rv_for)
        day = day_feats(feats, d, dec, chain, atm)
        return [{"date": str(d), **day, **c} for c in cand_feats(b, d, dec, chain)]
    except (runner.BadSnapshot, ValueError, IndexError, KeyError):
        return []


def chunk(job):
    days, labels = job
    cfg = config.load(NAME)
    b, books = book(cfg), {k: book(cfg, k) for k in DELTAS}
    root = engine.snapshots(b)
    feats, cache = pd.read_parquet(root / "features.parquet"), {}
    rv_for, end = engine.cached(cache, b["backtest"]["fit_years"]), engine.day(b["backtest"]["end"])
    X, Y = [], []
    for d in days:
        X += day_rows(b, feats, root, d, rv_for)
        if labels:
            for k in DELTAS:
                y = label(books[k], d, end, cache)
                Y += [{"date": str(d), "delta": k, **y}] if y else []
    return X, Y


def gather(days, labels):
    parts = [list(p) for p in np.array_split(np.array(days, dtype=object), 4 * WORKERS) if len(p)]
    X, Y = [], []
    with ProcessPoolExecutor(WORKERS) as ex:
        for i, (x, y) in enumerate(ex.map(chunk, [(p, labels) for p in parts])):
            X, Y = X + x, Y + y
            print(f"  part {i + 1}/{len(parts)} done", flush=True)
    return pd.DataFrame(X), pd.DataFrame(Y)


def dev_days(cfg):
    b = book(cfg)
    feats = pd.read_parquet(engine.snapshots(b) / "features.parquet")
    return engine.trading_days(feats, b["backtest"]["start"], b["backtest"]["end"])


def data(cfg):
    # built once; reused by --report-only
    fx, fy = WORK / "features.parquet", WORK / "labels.parquet"
    if not (fx.exists() and fy.exists()):
        WORK.mkdir(parents=True, exist_ok=True)
        X, Y = gather(dev_days(cfg), True)
        X.to_parquet(fx)
        Y.to_parquet(fy)
    return pd.read_parquet(fx), pd.read_parquet(fy)


# ---- ranker, walk-forward and picks ----

def panel(X, Y):
    # candidates with labels; skip scores 0
    df = X.merge(Y, on=["date", "delta"], how="left")
    sk = df["is_skip"] == 1
    df.loc[sk, ["pnl", "score"]] = 0.0
    df.loc[sk, "close"] = df.loc[sk, "date"]
    return df.sort_values(["date", "is_skip", "delta"], kind="stable").reset_index(drop=True)


def span(df, lo, hi):
    # labelled days in [lo, hi) closed before hi
    lab = df[df["score"].notna()]
    g = lab.groupby("date")
    ok = g["close"].max().lt(hi) & g["is_skip"].min().eq(0)
    days = [d for d in ok[ok].index if lo <= d < hi]
    return lab[lab["date"].isin(days)]


def grades(score, theta):
    return np.searchsorted(theta, np.asarray(score, float), side="left")  # paper eq. 8


def groups(df):
    return df.groupby("date", sort=False).size().to_numpy()


def fit(train, early):
    theta = np.percentile(train.loc[train["is_skip"] == 0, "score"], CUTS)
    m = lgb.LGBMRanker(**PARAMS)
    m.fit(train[FEATS], grades(train["score"], theta), group=groups(train),
          eval_X=early[FEATS], eval_y=grades(early["score"], theta), eval_group=[groups(early)],
          eval_at=[1], callbacks=[lgb.early_stopping(50, first_metric_only=True, verbose=False)])
    return m, theta


def ranked(m, df):
    # each day: top pick, top-two gap, best put
    s = df.assign(pred=m.predict(df[FEATS]))
    rows = []
    for d, g in s.groupby("date", sort=True):
        g = g.sort_values("pred", ascending=False, kind="stable")
        puts = g[g["is_skip"] == 0]
        rows.append({"date": d, "top": float(g["delta"].iloc[0]),
                     "gap": float(g["pred"].iloc[0] - g["pred"].iloc[1]) if len(g) > 1 else 0.0,
                     "best": float(puts["delta"].iloc[0]) if len(puts) else SKIP})
    return pd.DataFrame(rows), s[["date", "delta", "pred"]]


def sortino(x):
    down = math.sqrt(float(np.mean(np.minimum(x, 0) ** 2)))
    return float(np.mean(x)) / (down + 1e-8)


def realized(df, days, col):
    # label P&L of each day's pick; skip = 0
    pnl = df.set_index(["date", "delta"])["pnl"]
    return np.array([0.0 if k == SKIP else float(pnl.get((d, k), np.nan))
                     for d, k in zip(days["date"], days[col])])


def traded(days, tau):
    return (days["top"] != SKIP) & (days["gap"] >= tau)


def gate(days, pnl):
    # paper 3.5: tau maximises top-1 Sortino
    pnl = np.nan_to_num(pnl)
    grid = [0.0] + [float(q) for q in np.quantile(days["gap"], np.arange(0.1, 1.0, 0.1))]
    return max(grid, key=lambda t: (sortino(np.where(traded(days, t), pnl, 0.0)), -t))


def window(df, lo, hi):
    # one step: fit, early stop, gate, predict
    cal = (pd.Timestamp(lo) - GATE).strftime("%Y-%m-%d")
    stop = (pd.Timestamp(lo) - GATE - EARLY).strftime("%Y-%m-%d")
    train, early = span(df, "0000", stop), span(df, stop, cal)
    m, theta = fit(train, early)
    cal_days = span(df, cal, lo)["date"].unique()
    cdays, _ = ranked(m, df[df["date"].isin(cal_days)])
    tau = gate(cdays, realized(df, cdays, "top"))
    tdays, scored = ranked(m, df[(df["date"] >= lo) & (df["date"] < hi)])
    picks = pd.DataFrame({"date": tdays["date"],
                          "ltr": np.where(traded(tdays, tau), tdays["top"], SKIP),
                          "ltr_nogate": tdays["top"], "ltr_noskip": tdays["best"]})
    meta = {"test": lo, "fit_days": int(train["date"].nunique()),
            "early_days": int(early["date"].nunique()), "gate_days": len(cdays),
            "test_days": len(tdays), "rounds": int(m.best_iteration_ or PARAMS["n_estimators"]),
            "theta": [float(t) for t in theta], "tau": tau,
            "gate_trade_rate": float(traded(cdays, tau).mean()),
            "test_trade_rate": float((picks["ltr"] != SKIP).mean())}
    imp = pd.Series(m.booster_.feature_importance("gain"), index=FEATS, name=lo)
    return picks, scored, meta, imp


def walk(df, spans):
    out = [window(df, lo, hi) for lo, hi in spans]
    for _, _, meta, _ in out:
        print(f"  {meta['test']}: fit {meta['fit_days']} days, {meta['rounds']} rounds, "
              f"tau {meta['tau']:.3f}, trades {meta['test_trade_rate']:.0%}", flush=True)
    return (pd.concat([o[0] for o in out]), pd.concat([o[1] for o in out]),
            [o[2] for o in out], pd.concat([o[3] for o in out], axis=1))


def save_picks(picks, append=False):
    for v in VARIANTS:
        df = picks[["date", v]].rename(columns={v: "delta"})
        path = WORK / f"picks_{v}.parquet"
        if append:
            df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
        df.to_parquet(path)


def rank_dev(cfg):
    X, Y = data(cfg)
    df = panel(X, Y)
    spans = [(f"{y}-01-01", f"{y + 1}-01-01") for y in YEARS]
    picks, scored, meta, imp = walk(df, spans)
    save_picks(picks)
    scored.to_parquet(WORK / "scores.parquet")
    imp.to_parquet(WORK / "importance.parquet")
    (WORK / "windows.json").write_text(json.dumps(meta, indent=1))


def rank_holdout(cfg):
    # hold-out mode only: one window on dev labels
    X, Y = data(cfg)
    b = book(cfg)
    feats = pd.read_parquet(engine.snapshots(b) / "features.parquet")
    hx, _ = gather(engine.trading_days(feats, HOLDOUT[0], b["history"]["last_day"]), False)
    picks, _, meta, _ = walk(panel(pd.concat([X, hx], ignore_index=True), Y), [HOLDOUT])
    save_picks(picks, append=True)
    (WORK / "holdout_window.json").write_text(json.dumps(meta, indent=1))


# ---- report ----

def load_sets(cfg, holdout=False):
    ref = report.runs(REF, holdout)
    if not ref:
        raise SystemExit(f"no {'hold-out ' if holdout else ''}runs for {REF}")
    labels = [cfg["pass"]["primary"]] if holdout else list(cfg["variants"])
    return {"hedged": ref, **{v: report.runs(f"{NAME}/{v}", holdout) for v in labels}}


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, holdout=False):
    p, rows = cfg["pass"], []
    for c in p["check"]:
        if holdout and c["period"] != "all":
            continue
        for m in MULTS:
            v = value(tab, p["primary"], m, c["period"], c["metric"])
            r = value(tab, p["against"], m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def events(out, kind):
    # round_trip: closed positions
    return len(report.round_trips(out))


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if p.get("min_events", 0) and not holdout:
        n = events(sets[p["primary"]][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def cum_pnl(sets, path):
    fig, ax = plt.subplots(figsize=(7, 3.4))
    for i, (label, by_mult) in enumerate(sets.items()):
        for mult, out in sorted(by_mult.items()):
            d = report.daily(out).cumsum()
            ax.plot(d.index, d.values, report.STYLE.get(mult, ":"), color=report.color(i, label),
                    lw=1.1, label=f"{label} {mult:g}x")
    ax.axhline(0, color="k", lw=0.6)
    ax.axvline(pd.Timestamp(f"{YEARS[0]}-01-01"), color="k", lw=0.6, ls=":")
    ax.set(title="Cumulative net P&L (dotted: ranker starts)", ylabel="USD")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    return report.save(fig, path)


def drawdown(sets, path):
    fig, axes = plt.subplots(2, 1, figsize=(7, 4), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult in by_mult:
                eq = report.daily(by_mult[mult]).cumsum()
                ax.plot(eq.index, (eq - eq.cummax().clip(lower=0)).values,
                        color=report.color(i, label), lw=1, label=label)
        ax.axhline(-LIMIT, color="tab:red", lw=0.8, ls=":")
        ax.set(title=f"Drawdown, {mult:g}x spreads (dotted: stress budget)", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False, ncol=4)
    return report.save(fig, path)


def yearly(sets, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    n = len(sets)
    for ax, mult in zip(axes, MULTS):
        for i, (label, by_mult) in enumerate(sets.items()):
            if mult in by_mult:
                y = report.daily(by_mult[mult]).groupby(lambda t: t.year).sum()
                ax.bar(y.index + (i - (n - 1) / 2) * 0.8 / n, y.values, 0.8 / n,
                       color=report.color(i, label), label=label)
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L by year, {mult:g}x", ylabel="USD")
    axes[0].legend(fontsize=7, frameon=False, loc="lower left")
    return report.save(fig, path)


def standard(sets, folder):
    return [cum_pnl(sets, folder / "cum_pnl.png"), drawdown(sets, folder / "drawdown.png"),
            yearly(sets, folder / "yearly.png"), report.by_reason(sets, folder / "by_reason.png"),
            report.fees(sets, folder / "fees.png")]


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


def picks_mix(path):
    # share of test days per pick, by year
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    keys = [SKIP, *DELTAS]
    colors = ["0.6"] + [plt.cm.viridis(i / (len(DELTAS) - 1)) for i in range(len(DELTAS))]
    for ax, v in zip(axes, ("ltr", "ltr_noskip")):
        p = pd.read_parquet(WORK / f"picks_{v}.parquet")
        p = p[p["date"] < "2025-01-01"]
        share = pd.crosstab(p["date"].str[:4], p["delta"], normalize="index").reindex(
            columns=keys, fill_value=0.0)
        bottom = np.zeros(len(share))
        for k, c in zip(keys, colors):
            ax.bar(share.index, share[k], bottom=bottom, color=c, label="skip" if k == SKIP else f"{k:g}")
            bottom += share[k].to_numpy()
        ax.set(title=f"{v}: picks by test year", ylabel="share of days")
        ax.tick_params(axis="x", labelsize=7)
    axes[1].legend(fontsize=6, frameon=False, ncol=1, bbox_to_anchor=(1.0, 1.0), loc="upper left")
    return report.save(fig, path)


def label_table():
    # label-level: each day's pick vs fixed 25-delta
    X, Y = pd.read_parquet(WORK / "features.parquet"), pd.read_parquet(WORK / "labels.parquet")
    df = panel(X, Y)
    rows = []
    for v in ("ltr", "ltr_nogate", "ltr_noskip"):
        p = pd.read_parquet(WORK / f"picks_{v}.parquet")
        p = p[p["date"] < "2025-01-01"]
        rows.append(p.assign(book=v, pnl=realized(df, p, "delta")))
    p = rows[0][["date"]].assign(delta=0.25)
    rows.append(p.assign(book="fixed 0.25", pnl=realized(df, p, "delta")))
    best = df[df["score"].notna()].groupby("date")["pnl"].max()
    p = rows[0][["date"]].assign(book="best in hindsight", pnl=lambda x: x["date"].map(best))
    rows.append(p)
    t = pd.concat(rows, ignore_index=True).assign(year=lambda x: x["date"].str[:4],
                                                  pnl=lambda x: x["pnl"].fillna(0.0))
    return t.groupby(["book", "year"])["pnl"].agg(["mean", "count"]).reset_index()


def ranking(tab, path):
    fig, ax = plt.subplots(figsize=(7, 3))
    books = ["fixed 0.25", "ltr", "ltr_nogate", "ltr_noskip"]
    for i, b in enumerate(books):
        y = tab[tab["book"] == b]
        ax.bar(y["year"].astype(int) + (i - 1.5) * 0.2, y["mean"], 0.2, label=b,
               color="0.55" if i == 0 else report.COLORS[i])
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Label P&L of each day's pick, mean per test day, 1x", ylabel="USD per day")
    ax.legend(fontsize=7, frameon=False, ncol=4)
    return report.save(fig, path)


def importance(path):
    imp = pd.read_parquet(WORK / "importance.parquet")
    share = (imp / imp.sum()).mean(axis=1).sort_values().tail(15)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.barh(share.index, share.values, color="tab:blue")
    ax.set(title="Feature gain share, mean of 8 windows (top 15)", xlabel="share of total gain")
    ax.tick_params(axis="y", labelsize=7)
    return report.save(fig, path)


def entries(sets):
    # executed entries by picked delta, 1x
    rows = []
    for v in VARIANTS:
        p = pd.read_parquet(WORK / f"picks_{v}.parquet").set_index("date")["delta"]
        rt = report.round_trips(sets[v][1.0])
        rt = rt.assign(pick=rt["entry_date"].map(p).fillna(0.25), year=rt["entry_date"].str[:4])
        rt = rt[rt["year"] >= str(YEARS[0])]
        g = rt.groupby("pick").agg(trips=("pick", "size"), net=("pnl_net", "sum")).reset_index()
        rows.append(g.assign(book=v))
    return pd.concat(rows, ignore_index=True)


def extra(cfg, sets, folder):
    # picks, label-level ranking, feature gain
    meta = pd.DataFrame(json.loads((WORK / "windows.json").read_text()))
    show(folder, "windows", meta.drop(columns=["theta"]))
    tab = label_table()
    show(folder, "label_pnl", tab)
    show(folder, "entries_by_pick", entries(sets))
    return [picks_mix(folder / "picks.png"), ranking(tab, folder / "ranking.png"),
            importance(folder / "importance.png")]


def build(cfg, holdout=False):
    sets = load_sets(cfg, holdout)
    folder = FIGS / "holdout" if holdout else FIGS
    tab = report.table(sets)
    folder.mkdir(parents=True, exist_ok=True)
    tab.to_csv(folder / "table.csv", index=False)
    paths = [cum_pnl(sets, folder / "cum_pnl.png")] if holdout else (
        standard(sets, folder) + extra(cfg, sets, folder))
    chk = checks(cfg, tab, holdout)
    chk.to_csv(folder / "pass_bar.csv", index=False)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades",
            "win_rate", "gross", "option_fees", "hedge_fees", "hedge_orders"]
    print(tab[cols].round(2).to_string(index=False))
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk, holdout)}")
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')}; "
          f"reference {REF} reused, not rerun)")
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    p.add_argument("--holdout", action="store_true", help="final run: primary variant, once")
    a = p.parse_args()
    cfg = config.load(NAME)
    if a.holdout and not a.report_only:
        if not report.runs(REF, True):
            raise SystemExit(f"run the {REF} hold-out first; it is the reference")
        rank_holdout(cfg)
        for label, rows in run.holdout(NAME, cfg["pass"]["primary"], cfg, config.load()).items():
            print(f"\n{label} (hold-out)\n{run.table(rows)}")
    elif not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        rank_dev(cfg)
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}")
    build(cfg, a.holdout)


if __name__ == "__main__":
    main()
