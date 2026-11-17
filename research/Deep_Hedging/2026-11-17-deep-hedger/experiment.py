"""2026-11-17-deep-hedger: walk-forward deep hedger on the live put20 book.

python research/Deep_Hedging/2026-11-17-deep-hedger/experiment.py            # train, run, report
python research/Deep_Hedging/2026-11-17-deep-hedger/experiment.py --report-only
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import episodes as E  # noqa: E402
import train as TR  # noqa: E402

from lsgamma import experiments  # noqa: E402
from lsgamma.backtest import config, deep_hedge, engine, report, run  # noqa: E402

NAME = "2026-11-17-deep-hedger"
FIGS = HERE / "figures"
OUT = experiments.ROOT / NAME
MULTS = (1.0, 2.0)
PERIODS = [("all", None, None), ("2014-2016", None, "2017-01-01"),
           ("2017-2020", "2017-01-01", "2021-01-01"), ("2021-2024", "2021-01-01", None),
           ("2017-2024", "2017-01-01", None)]
RULES = {
    "higher": lambda v, r, x: v > r,
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "at_most": lambda v, r, x: v <= x,  # absolute
}
COLORS = {"put20": "#444444", "const": "tab:orange", "deep": "tab:blue"}


# ---------------------------------------------------------------- training
def ensemble_fn(nets):
    return lambda x: torch.stack([n(x) for n in nets]).mean(0)


def train_all(cfg):
    tr = cfg["train"]
    vcfg = config.variant(NAME, "put20")
    ex = {**vcfg["backtest"], **vcfg["exit"], "spread_mult": 1.0}
    if not (OUT / "panel_daily.parquet").exists():
        E.save_panel(NAME, *E.build_panel(vcfg, engine.day(vcfg["backtest"]["start"]),
                                          engine.day(vcfg["backtest"]["end"])))
    daily, puts = E.load_panel(NAME)
    eps = E.episodes(daily, puts, date(tr["last_year"] + 1, 1, 1))
    grid = [round(i * tr["const_step"], 4)
            for i in range(int(round(deep_hedge.MAX_RATIO / tr["const_step"])) + 1)]
    pol_c, pol_d, log = {}, {}, []
    for y in range(tr["first_year"], tr["last_year"] + 1):
        cut = date(y, 1, 1)
        fit = [e for e in eps if e["exit"] < cut]
        test = [e for e in eps if e["entry"].year == y]
        Tf, Tt = E.tensors(fit), E.tensors(test)
        tf, tt = TR.to_torch(Tf), TR.to_torch(Tt)
        ref = TR.evaluate(tf, ex, TR.const_fn(1.0))
        c, _ = TR.fit_const(tf, ex, grid, tr["kappa"], torch.tensor(ref["cvar95"]))
        hp = {k: tr[k] for k in ("hidden", "lr", "epochs", "weight_decay", "kappa")}
        nets = [TR.fit_net(Tf, tf, ex, hp, s, torch.tensor(ref["cvar95"])) for s in tr["seeds"]]
        pol_c[str(y)] = {"const": c}
        pol_d[str(y)] = {"members": [n.export() for n in nets]}
        check_inference(nets, pol_d[str(y)], tt)
        for split, t in (("train", tf), ("next_year", tt)):
            for book, fn in (("delta", TR.const_fn(1.0)), ("const", TR.const_fn(c)),
                             ("deep", ensemble_fn(nets))):
                log.append({"year": y, "split": split, "book": book, "const": c,
                            **TR.evaluate(t, ex, fn)})
        print(f"{y}: {len(fit)} training episodes, const {c}")
    for name, pol in (("policy_const.json", pol_c), ("policy_deep.json", pol_d)):
        (OUT / name).write_text(json.dumps({"experiment": NAME, "years": pol}))
    df = pd.DataFrame(log)
    df.to_csv(OUT / "train_log.csv", index=False)
    return df


def check_inference(nets, model, t):
    # engine's numpy forward must match torch
    x = torch.cat([t["X"][:, 0], torch.zeros(t["X"].shape[0], 1, dtype=torch.float64)], 1)[:50]
    with torch.no_grad():
        want = torch.stack([n(x) for n in nets]).mean(0).numpy()
    got = np.array([deep_hedge.ratio(model, r) for r in x.numpy()])
    assert np.allclose(want, got, atol=1e-9), "numpy inference differs from torch"


def digest(name):
    return hashlib.sha256((OUT / name).read_bytes()).hexdigest()[:12]


# ---------------------------------------------------------------- report
def table(sets):
    rows = []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            for period, lo, hi in PERIODS:
                rows.append({"label": label, "mult": mult, "period": period,
                             **report.stats(out, lo, hi)})
    return pd.DataFrame(rows)


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab):
    p, rows = cfg["pass"], []
    for c in p["check"]:
        against = c.get("against", p["against"])
        for m in MULTS:
            v = value(tab, p["primary"], m, c["period"], c["metric"])
            r = value(tab, against, m, c["period"], c["metric"])
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} "
                                  f"({c['period']}) vs {against}",
                         "mult": m, "deep": v, "against": r,
                         "pass": RULES[c["rule"]](v, r, c.get("value", 0.0))})
    return pd.DataFrame(rows)


def verdict(cfg, tab, chk):
    n = int(value(tab, cfg["pass"]["primary"], 1.0, "2017-2024", "trades"))
    if n < cfg["pass"]["min_events"]:
        return f"INCONCLUSIVE ({n} round trips < {cfg['pass']['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def ratios(out):
    ev = out["events"]
    ev = ev[ev["event"] == "deep_ratio"]
    return pd.Series(ev["detail"].astype(float).to_numpy(), index=pd.to_datetime(ev["date"]))


def charts(sets, folder):
    paths = []
    fig, axes = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for label, by_mult in sets.items():
            d = report.daily(by_mult[mult]).cumsum()
            ax.plot(d.index, d.values, color=COLORS[label], lw=1.1, label=label)
        ax.axvline(pd.Timestamp("2017-01-01"), color="k", lw=0.6, ls=":")
        ax.set(title=f"Cumulative net P&L, {mult:g}x spreads (dotted: models switch on)",
               ylabel="USD")
    axes[0].legend(frameon=False, fontsize=8)
    paths.append(report.save(fig, folder / "cum_pnl.png"))

    fig, axes = plt.subplots(2, 1, figsize=(7.5, 4.5), sharex=True)
    for ax, mult in zip(axes, MULTS):
        for label, by_mult in sets.items():
            eq = report.daily(by_mult[mult]).cumsum()
            ax.plot(eq.index, (eq - eq.cummax().clip(lower=0)).values, color=COLORS[label],
                    lw=1, label=label)
        ax.axhline(-87500, color="tab:red", lw=0.8, ls=":")
        ax.set(title=f"Drawdown, {mult:g}x (dotted: stress budget)", ylabel="USD")
    axes[0].legend(frameon=False, fontsize=8)
    paths.append(report.save(fig, folder / "drawdown.png"))

    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    n = len(sets)
    for i, (label, by_mult) in enumerate(sets.items()):
        y = report.daily(by_mult[1.0]).groupby(lambda t: t.year).sum()
        ax.bar(y.index + (i - (n - 1) / 2) * 0.8 / n, y.values, 0.8 / n, color=COLORS[label],
               label=label)
    ax.axhline(0, color="k", lw=0.6)
    ax.set(title="Net P&L by year, 1x", ylabel="USD")
    ax.legend(frameon=False, fontsize=8)
    paths.append(report.save(fig, folder / "yearly.png"))

    fig, ax = plt.subplots(figsize=(7.5, 3))
    for label in ("deep", "const"):
        r = ratios(sets[label][1.0])
        ax.plot(r.index, r.values, ".", ms=2, color=COLORS[label], label=label)
    ax.axhline(1, color="k", lw=0.6)
    ax.set(title="Hedge share of delta used each morning (1x)", ylabel="ratio", ylim=(0, 1.55))
    ax.legend(frameon=False, fontsize=8)
    paths.append(report.save(fig, folder / "ratio.png"))
    return paths


def by_reason(sets):
    rows = []
    for label, by_mult in sets.items():
        rt = report.between(report.round_trips(by_mult[1.0]), "exit_date", "2017-01-01", None)
        for reason, g in rt.groupby("reason"):
            rows.append({"book": label, "reason": reason, "n": len(g),
                         "pnl_net": round(g["pnl_net"].sum())})
    return pd.DataFrame(rows)


def ratio_profile(sets):
    # deep ratio by VIX bucket, from the engine's own log
    out = sets["deep"][1.0]
    r = ratios(out)
    feats = pd.read_parquet(engine.DATA / "v1" / "features.parquet")
    vix = feats["vix"].shift(1).reindex(r.index)  # previous close, as the model saw
    b = pd.cut(vix, [0, 13, 16, 20, 25, 35, 100])
    return r.groupby(b, observed=True).agg(["count", "mean", "min", "max"]).round(3).reset_index()


def show(folder, name, df):
    df.to_csv(folder / f"{name}.csv", index=False)
    print(f"\n{name}\n{df.round(3).to_string(index=False)}")


def build(cfg):
    sets = {v: report.runs(f"{NAME}/{v}") for v in cfg["variants"]}
    FIGS.mkdir(parents=True, exist_ok=True)
    tab = table(sets)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades", "win_rate",
            "hedge_fees", "hedge_orders"]
    show(FIGS, "table", tab[cols])
    chk = checks(cfg, tab)
    show(FIGS, "pass_bar", chk)
    show(FIGS, "exits_2017_2024", by_reason(sets))
    show(FIGS, "ratio_by_vix", ratio_profile(sets))
    log = pd.read_csv(OUT / "train_log.csv")
    show(FIGS, "walk_forward_per_contract",
         log.pivot_table(index=["year", "split"], columns="book", values="mean").reset_index())
    show(FIGS, "walk_forward_cvar95",
         log.pivot_table(index=["year", "split"], columns="book", values="cvar95").reset_index())
    paths = charts(sets, FIGS)
    print(f"\nverdict: {verdict(cfg, tab, chk)}")
    print(f"trials: {report.trials(NAME)}  policies: const {digest('policy_const.json')}, "
          f"deep {digest('policy_deep.json')}")
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    a = p.parse_args()
    cfg = config.load(NAME)
    if not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        train_all(cfg)
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}")
    build(cfg)


if __name__ == "__main__":
    main()
