"""2026-11-17-deep-hedger-v2: bounded, risk-priced deep hedger on the live put20 book.

python research/Deep_Hedging/2026-11-17-deep-hedger-v2/experiment.py            # train, evaluate, run, report
python research/Deep_Hedging/2026-11-17-deep-hedger-v2/experiment.py --report-only
"""
import argparse
import hashlib
import json
import multiprocessing as mp
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import torch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from lib import baselines, evaluate, hedger as H, panel  # noqa: E402

from lsgamma import experiments  # noqa: E402
from lsgamma.backtest import config, deep_hedge, engine, report, run  # noqa: E402

NAME = "2026-11-17-deep-hedger-v2"
FIGS = HERE / "figures"
OUT = experiments.ROOT / NAME
MULTS = (1.0, 2.0)
PERIODS = [("all", None, None), ("2014-2016", None, "2017-01-01"),
           ("2017-2020", "2017-01-01", "2021-01-01"), ("2021-2024", "2021-01-01", None),
           ("2017-2024", "2017-01-01", None)]
RULES = {
    "higher": lambda v, r, x: v > r,
    "above": lambda v, r, x: v > x,  # absolute
    "not_below": lambda v, r, x: v >= r - x,
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "at_most": lambda v, r, x: v <= x,  # absolute
}
NETS = ["linear", "deep", "deep_l025", "deep_l1"]
COLORS = {"put20": "#444444", "hw": "tab:green", "linear": "tab:orange", "deep": "tab:blue",
          "deep_l025": "tab:purple", "deep_l1": "tab:cyan"}


def ex_for(cfg, mult=1.0):
    v = config.variant(NAME, "deep")
    return {**v["backtest"], **v["exit"], **v["hedge"], "spread_mult": mult}


# ---------------------------------------------------------------- training
def windows(eps, y, val_share):
    # fit: exit before split; val: entry on or after split; both before 1 Jan y
    cut = date(y, 1, 1)
    known = [e for e in eps if e["exit"] < cut]
    split = sorted(e["entry"] for e in known)[int(len(known) * (1 - val_share))]
    fit = [e for e in known if e["exit"] < split]
    val = [e for e in known if e["entry"] >= split]
    test = [e for e in eps if e["entry"].year == y]
    return fit, val, test, split


def jobs_for(tr, lams, ex, paths):
    jobs = []
    for y, path in paths.items():
        specs = [(v, lams[v], tr["seeds"], [] if v == "linear" else tr["hidden"]) for v in NETS]
        specs += [(f"deep_seeds{i + 1}", lams["deep"], s, tr["hidden"])
                  for i, s in enumerate(tr["robust_seeds"])]
        for v, lam, seeds, hidden in specs:
            hp = {k: tr[k] for k in ("lr", "epochs", "eval_every", "weight_decay", "lo", "hi")}
            for s in seeds:
                jobs.append({"key": (v, y, s), "data": str(path), "lam": lam, "seed": s,
                             "ex": ex, "hp": {**hp, "hidden": hidden}})
    return jobs


def train_all(cfg):
    tr, lams = cfg["train"], cfg["lam"]
    vcfg = config.variant(NAME, "deep")
    ex = ex_for(cfg)
    daily, puts = panel.load()
    eps = H.episodes(daily, puts, vcfg, date(tr["last_year"] + 1, 1, 1), tuple(tr["targets"]))
    (OUT / "cache").mkdir(parents=True, exist_ok=True)
    paths, tests, info = {}, {}, []
    for y in range(tr["first_year"], tr["last_year"] + 1):
        fit, val, test, split = windows(eps, y, tr["val_share"])
        paths[y] = OUT / "cache" / f"{y}.pkl"
        with open(paths[y], "wb") as f:
            pickle.dump((H.tensors(fit), H.tensors(val)), f)
        tests[y] = test
        info.append({"year": y, "fit": len(fit), "val": len(val), "test": len(test),
                     "split": str(split)})
    print(pd.DataFrame(info).to_string(index=False))
    jobs = jobs_for(tr, lams, ex, paths)
    with ProcessPoolExecutor(max(1, mp.cpu_count() - 2), mp_context=mp.get_context("spawn")) as pool:
        done = list(pool.map(H.train_cached, jobs, chunksize=1))
    members, log = {}, []
    for r in done:
        v, y, s = r["key"]
        members.setdefault(v, {}).setdefault(y, []).append((s, r["member"]))
        log.append({"variant": v, "year": y, "seed": s, "best_epoch": r["best_epoch"],
                    "val_start": r["val_start"], "val_best": r["val_best"]})
    hp = {"lo": tr["lo"], "hi": tr["hi"]}
    models = {v: {y: H.model_json([m for _, m in sorted(ms)], hp) for y, ms in by_y.items()}
              for v, by_y in members.items()}
    coefs = baselines.fit_walk_forward(daily, puts, range(tr["first_year"], tr["last_year"] + 1))
    models["hw"] = {y: {"kind": "hw", "coef": [c["a"], c["b"], c["c"]], "lo": tr["lo"],
                        "hi": tr["hi"]} for y, c in coefs.items()}
    for v, by_y in models.items():
        (OUT / f"policy_{v}.json").write_text(json.dumps(
            {"experiment": NAME, "years": {str(y): m for y, m in by_y.items()}}))
    pd.DataFrame(log).to_csv(OUT / "train_log.csv", index=False)
    pd.DataFrame([{"year": y, **c} for y, c in coefs.items()]).to_csv(OUT / "hw_coef.csv",
                                                                      index=False)
    check_inference(models, tests)
    paired_eval(cfg, models, tests)


def check_inference(models, tests):
    # engine numpy forward must match the torch policy, every model kind, mixed path inputs
    rng = np.random.default_rng(0)
    for v, by_y in models.items():
        for y, model in by_y.items():
            T = H.tensors(tests[y][:40])
            pol = H.from_json(model)
            k = 3
            d = {n: torch.tensor(np.nan_to_num(x[:, k]), dtype=torch.float64)
                 for n, x in T["X"].items()}
            n = len(T["P0"])
            d["pnl_frac"] = torch.tensor(rng.normal(0, 0.5, n), dtype=torch.float64)
            d["hold_frac"] = torch.tensor(rng.uniform(0.7, 1.3, n), dtype=torch.float64)
            with torch.no_grad():
                want = pol(d).numpy()
            got = np.array([deep_hedge.ratio(model, {a: float(b[i]) for a, b in d.items()})
                            for i in range(n)])
            assert np.allclose(want, got, atol=1e-9), f"inference mismatch: {v} {y}"


def paired_eval(cfg, models, tests):
    # every policy on the SAME out-of-sample episodes (entries in year y, model y)
    rows = []
    for y, test in tests.items():
        for mult in MULTS:
            T = H.tensors(test, mult)
            t = H.to_torch(T)
            pols = {"put20": H.delta_policy,
                    **{v: H.from_json(models[v][y]) for v in models}}
            for v, pol in pols.items():
                with torch.no_grad():
                    pnl = H.rollout(t, pol, ex_for(cfg, mult)).numpy()
                rows += [{"year": y, "mult": mult, "policy": v, "entry": e, "target": g, "pnl": p}
                         for e, g, p in zip(T["entry"], T["target"], pnl)]
    pd.DataFrame(rows).to_parquet(OUT / "paired.parquet")


# ---------------------------------------------------------------- report
def paired_table(cfg, target=0.20):
    df = pd.read_parquet(OUT / "paired.parquet")
    df = df[np.isclose(df["target"], target)]
    tr, rows, years = cfg["train"], [], {}
    for mult in MULTS:
        d = df[df["mult"] == mult].pivot_table(index="entry", columns="policy", values="pnl")
        months = np.array([f"{e:%Y-%m}" for e in d.index])
        for v in d.columns.drop("put20"):
            diff = (d[v] - d["put20"]).to_numpy()
            b = evaluate.block_bootstrap(diff, months, tr["n_boot"], tr["block"], tr["boot_seed"])
            share, per = evaluate.share_positive_years(diff, list(d.index))
            rows.append({"policy": v, "mult": mult, "n": b["n"], "mean_gain": b["mean"],
                         "lo": b["lo"], "hi": b["hi"], "p_le0": b["p_le0"],
                         "pos_years": share, "cvar95": evaluate.cvar(d[v].to_numpy()),
                         "cvar95_put20": evaluate.cvar(d["put20"].to_numpy())})
            years[(v, mult)] = per
    return pd.DataFrame(rows), years


def table(sets):
    rows = []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            for period, lo, hi in PERIODS:
                rows.append({"label": label, "mult": mult, "period": period,
                             **report.stats(out, lo, hi)})
    return pd.DataFrame(rows)


def value(tab, paired, label, mult, period, metric):
    if metric == "paired_lo":
        return float(paired[(paired["policy"] == label) & (paired["mult"] == mult)]["lo"].iloc[0])
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, paired, primary=None):
    p, rows = cfg["pass"], []
    primary = primary or p["primary"]
    for c in p["check"]:
        against = c.get("against", p["against"])
        if against == primary:
            continue
        for m in MULTS:
            v = value(tab, paired, primary, m, c["period"], c["metric"])
            r = math_nan() if c["metric"] == "paired_lo" else value(tab, paired, against, m,
                                                                   c["period"], c["metric"])
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} "
                                  f"({c['period']}) vs {against}",
                         "mult": m, primary: v, "against": r,
                         "pass": bool(RULES[c["rule"]](v, r, c.get("value", 0.0)))})
    return pd.DataFrame(rows)


def math_nan():
    return float("nan")


def verdict(cfg, tab, chk):
    n = int(value(tab, None, cfg["pass"]["primary"], 1.0, "2017-2024", "trades"))
    if n < cfg["pass"]["min_events"]:
        return f"INCONCLUSIVE ({n} round trips < {cfg['pass']['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def ratios(out):
    ev = out["events"]
    ev = ev[ev["event"] == "deep_ratio"]
    return pd.Series(ev["detail"].astype(float).to_numpy(), index=pd.to_datetime(ev["date"]))


def ratio_profile(sets):
    feats = pd.read_parquet(engine.DATA / "v1" / "features.parquet")
    rows = []
    for v in ("hw", "linear", "deep"):
        r = ratios(sets[v][1.0])
        vix = feats["vix"].shift(1).reindex(r.index)  # previous close, as the model saw
        g = r.groupby(pd.cut(vix, [0, 13, 16, 20, 25, 35, 100]), observed=True).mean()
        rows.append({"policy": v, **{str(k): round(x, 3) for k, x in g.items()},
                     "mean": round(r.mean(), 3)})
    return pd.DataFrame(rows)


def ex_2020(sets, mult=1.0):
    # engine P&L gain vs put20 without 19 Feb-30 Apr 2020
    base = report.daily(sets["put20"][mult])
    rows = []
    for v in sets:
        if v == "put20":
            continue
        d = report.daily(sets[v][mult]).sub(base, fill_value=0)["2017":]
        crash = d["2020-02-19":"2020-04-30"].sum()
        rows.append({"policy": v, "gain_2017_2024": d.sum(), "gain_feb_apr_2020": crash,
                     "gain_without": d.sum() - crash})
    return pd.DataFrame(rows)


def charts(sets, years, folder):
    paths = []
    fig, axes = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for label, by_mult in sets.items():
            d = report.daily(by_mult[mult]).cumsum()
            ax.plot(d.index, d.values, color=COLORS[label], lw=1.1 if label != "deep" else 1.6,
                    label=label)
        ax.axvline(pd.Timestamp("2017-01-01"), color="k", lw=0.6, ls=":")
        ax.set(title=f"Cumulative net P&L, {mult:g}x spreads (dotted: models switch on)",
               ylabel="USD")
    axes[0].legend(frameon=False, fontsize=7, ncol=3)
    paths.append(report.save(fig, folder / "cum_pnl.png"))

    fig, axes = plt.subplots(2, 1, figsize=(7.5, 4.5), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for label in ("put20", "hw", "linear", "deep"):
            eq = report.daily(sets[label][mult]).cumsum()
            ax.plot(eq.index, (eq - eq.cummax().clip(lower=0)).values, color=COLORS[label],
                    lw=1, label=label)
        ax.axhline(-87500, color="tab:red", lw=0.8, ls=":")
        ax.set(title=f"Drawdown, {mult:g}x (dotted: stress budget)", ylabel="USD")
    axes[0].legend(frameon=False, fontsize=7, ncol=4)
    paths.append(report.save(fig, folder / "drawdown.png"))

    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    labels = ["hw", "linear", "deep"]
    for i, v in enumerate(labels):
        per = years[(v, 1.0)]
        ax.bar(per.index + (i - 1) * 0.27, per.values, 0.27, color=COLORS[v], label=v)
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Paired gain per 20-delta trade vs put20, by entry year (1x, out of sample)",
           ylabel="USD per trade")
    ax.legend(frameon=False, fontsize=8)
    paths.append(report.save(fig, folder / "paired_by_year.png"))

    fig, ax = plt.subplots(figsize=(7.5, 3))
    for v in ("hw", "linear", "deep"):
        r = ratios(sets[v][1.0])
        ax.plot(r.index, r.values, ".", ms=2, color=COLORS[v], label=v)
    ax.axhline(1, color="k", lw=0.6)
    ax.set(title="Hedge share of delta used each morning (1x)", ylabel="ratio", ylim=(0.75, 1.25))
    ax.legend(frameon=False, fontsize=8, ncol=3)
    paths.append(report.save(fig, folder / "ratio.png"))
    return paths


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


def digest(name):
    return hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:12]


def same_before(sets):
    # models switch on in 2017: every variant must equal put20 before then
    for v, by_mult in sets.items():
        for m, out in by_mult.items():
            a = report.daily(out)[:"2016-12-31"]
            b = report.daily(sets["put20"][m])[:"2016-12-31"]
            assert np.allclose(a.values, b.reindex(a.index).values), f"{v} {m}x differs pre-2017"


def reconcile(sets):
    # simulator vs engine on the engine's own put20 trades before 2017 (no OOS data)
    cfg = config.variant(NAME, "deep")
    daily, puts = panel.load()
    eps = H.episodes(daily, puts, cfg, date(2017, 1, 1), (0.20,))
    by_day = {e["entry"]: e for e in eps}
    rt = report.round_trips(sets["put20"][1.0])
    rt = rt[pd.to_datetime(rt["exit_date"]) < "2017-01-01"]
    pick = [by_day.get(date.fromisoformat(d)) for d in rt["entry_date"]]
    keep = [i for i, e in enumerate(pick) if e is not None]
    T = H.tensors([pick[i] for i in keep])
    with torch.no_grad():
        sim = H.rollout(H.to_torch(T), H.delta_policy, ex_for(cfg)).numpy()
    eng = rt["pnl_net"].to_numpy()[keep]
    return pd.DataFrame([{"trades": len(rt), "matched": len(keep),
                          "corr": float(np.corrcoef(sim, eng)[0, 1]),
                          "median_abs_gap": float(np.median(np.abs(sim - eng))),
                          "sim_total": float(sim.sum()), "engine_total": float(eng.sum())}])


def build(cfg):
    sets = {"put20": report.runs(cfg["pass"]["reference"]),
            **{v: report.runs(f"{NAME}/{v}") for v in cfg["variants"]}}
    FIGS.mkdir(parents=True, exist_ok=True)
    same_before(sets)
    show(FIGS, "reconcile_pre2017", reconcile(sets))
    tab = table(sets)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades", "win_rate",
            "hedge_fees", "hedge_orders"]
    show(FIGS, "table", tab[cols])
    paired, years = paired_table(cfg)
    show(FIGS, "paired", paired)
    show(FIGS, "paired_by_year", pd.DataFrame({f"{v} {m:g}x": s for (v, m), s in years.items()}
                                              ).reset_index(names="year"))
    chk = checks(cfg, tab, paired)
    show(FIGS, "pass_bar", chk)
    for v in ("hw", "linear", "deep_l025", "deep_l1"):  # reported, cannot pass this card
        c = checks(cfg, tab, paired, primary=v)
        print(f"\n{v} against the same bar (sensitivity): "
              f"{int(c['pass'].sum())}/{len(c)} checks pass; failing: "
              f"{sorted(set(c.loc[~c['pass'], 'check']))}")
    show(FIGS, "ex_feb_apr_2020", ex_2020(sets))
    show(FIGS, "ratio_by_vix", ratio_profile(sets))
    log = pd.read_csv(OUT / "train_log.csv")
    show(FIGS, "early_stopping", log.groupby(["variant", "year"]).agg(
        best_epoch=("best_epoch", "median"), stopped_at_delta=("best_epoch", lambda s: (s == 0).mean()),
        val_gain=("val_best", "mean")).reset_index())
    show(FIGS, "hw_coef", pd.read_csv(OUT / "hw_coef.csv"))
    paths = charts(sets, years, FIGS)
    print(f"\nverdict: {verdict(cfg, tab, chk)}")
    print(f"trials: {report.trials(NAME)} (reference {cfg['pass']['reference']} reused)  "
          f"policies: " + ", ".join(f"{v} {digest(f'policy_{v}.json')}" for v in cfg["variants"]))
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    a = p.parse_args()
    cfg = config.load(NAME)
    if not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        if not report.runs(cfg["pass"]["reference"]):
            raise SystemExit(f"no runs for {cfg['pass']['reference']}")
        train_all(cfg)
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}", flush=True)
    build(cfg)


if __name__ == "__main__":
    main()
