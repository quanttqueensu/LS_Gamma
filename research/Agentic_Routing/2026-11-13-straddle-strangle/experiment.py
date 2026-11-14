import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-11-13-straddle-strangle"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
MULTS = (1.0, 2.0)
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
}


def load_sets(cfg, holdout=False):
    # baseline first so it is drawn grey
    ref = report.baseline(config.load(), holdout)
    labels = [cfg["pass"]["primary"]] if holdout else list(cfg["variants"])
    return {"baseline": ref, **{v: report.runs(f"{NAME}/{v}", holdout) for v in labels}}


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
            r = value(tab, p.get("against", "baseline"), m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def vol(out, lo=None, hi=None):
    # std of daily net P&L, USD
    d = report.daily(out)
    d = d[(d.index >= pd.Timestamp(lo or "1900")) & (d.index < pd.Timestamp(hi or "2100"))]
    return float(d.std())


def with_vol(sets, tab):
    spans = {"all": (None, None), "2014-2019": (None, report.SPLIT), "2020-2024": (report.SPLIT, None)}
    return tab.assign(vol=[vol(sets[r.label][r.mult], *spans[r.period]) for r in tab.itertuples()])


def structures(out):
    # opened structures by side (legs share a group)
    t = out["trades"]
    if "group" not in t:
        return {}
    o = t[(t["action"] == "open") & t["group"].notna()]
    return o.groupby("side")["group"].nunique().to_dict()


def verdict(cfg, sets, chk):
    p = cfg["pass"]
    if p.get("min_events", 0):
        n = structures(sets[p.get("event_label", p["primary"])][1.0])
        low = {k: n.get(k, 0) for k in ("long", "short") if n.get(k, 0) < p["min_events"]}
        if low:
            return f"INCONCLUSIVE (structures {low} < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def vol_by_year(sets, path):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for i, (label, by) in enumerate(sets.items()):
        d = report.daily(by[1.0])
        y = d.groupby(d.index.year).std()
        ax.plot(y.index, y.values, marker="o", ms=3, color=report.color(i, label), label=label)
    ax.set(title="Daily net P&L volatility by year, 1x (std, USD)", ylabel="USD per day")
    ax.legend(fontsize=8, ncol=4)
    return report.save(fig, path)


def by_side(sets, path):
    labels = list(sets)
    rows = {k: report.round_trips(sets[k][1.0]).groupby("side")["pnl_net"].sum() for k in labels}
    fig, ax = plt.subplots(figsize=(8, 3.6))
    w = 0.38
    for j, side in enumerate(("long", "short")):
        vals = [rows[k].get(side, 0.0) for k in labels]
        ax.bar([i + (j - 0.5) * w for i in range(len(labels))], vals, w,
               color="tab:blue" if side == "long" else "tab:orange",
               label="long gamma (call / straddle)" if side == "long" else "short gamma (put / strangle)")
    ax.axhline(0, color="0.3", lw=0.8)
    ax.set_xticks(range(len(labels)), labels)
    ax.set(title="Net P&L by side, 1x (options + hedges, after fees)", ylabel="USD")
    ax.legend(fontsize=8)
    return report.save(fig, path)


def extra(cfg, sets, folder):
    return [vol_by_year(sets, folder / "vol_by_year.png"), by_side(sets, folder / "by_side.png")]


def build(cfg, holdout=False):
    sets = load_sets(cfg, holdout)
    folder = FIGS / "holdout" if holdout else FIGS
    tab = with_vol(sets, report.table(sets))
    folder.mkdir(parents=True, exist_ok=True)
    tab.to_csv(folder / "table.csv", index=False)
    paths = [report.cum_pnl(sets, folder / "cum_pnl.png")] if holdout else (
        report.standard(sets, folder) + extra(cfg, sets, folder))
    chk = checks(cfg, tab, holdout)
    chk.to_csv(folder / "pass_bar.csv", index=False)
    cols = ["label", "mult", "period", "pnl", "vol", "sharpe", "max_dd", "es_5", "trades",
            "win_rate", "gross", "option_fees", "hedge_fees", "hedge_orders"]
    print(tab[cols].round(2).to_string(index=False))
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nstructures at 1x: { {k: structures(v[1.0]) for k, v in sets.items()} }")
    print(f"\nverdict: {verdict(cfg, sets, chk)}")
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')})")
    print("figures:", *[p.name for p in paths])


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    p.add_argument("--holdout", action="store_true", help="final run: primary variant, once")
    a = p.parse_args()
    cfg = config.load(NAME)
    if a.holdout and not a.report_only:
        for label, rows in run.holdout(NAME, cfg["pass"]["primary"], cfg, config.load()).items():
            print(f"\n{label} (hold-out)\n{run.table(rows)}")
    elif not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}")
    build(cfg, a.holdout)


if __name__ == "__main__":
    main()
