import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, metrics, report, run

NAME = "2026-11-11-trend-long-band"  # matches configs/experiments/<NAME>.toml
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


def events(out, name):
    # engine events, e.g. hedges the trend band held
    ev = out["events"]
    return int((ev["event"] == name).sum()) if len(ev) else 0


def verdict(cfg, sets, chk):
    p = cfg["pass"]
    if p.get("min_events", 0):
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} events < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def split(out):
    # round trips: option vs share-hedge P&L
    o, c = metrics.pairs(out["trades"])
    o, c = o.reset_index(drop=True), c.reset_index(drop=True)
    opt = c["side"].map({"long": 1, "short": -1}) * (c["price"] - o["price"]) * c["qty"] * 100
    return pd.DataFrame({"side": c["side"], "option": opt, "hedge": c["pnl"] - opt, "net": c["pnl_net"]})


def long_split(sets, folder):
    labels = list(sets)
    rows = pd.DataFrame([split(sets[l][1.0]).query("side == 'long'")[["option", "hedge", "net"]].sum()
                         for l in labels], index=labels)
    rows.to_csv(folder / "long_split.csv")
    fig, ax = plt.subplots(figsize=(7, 3.2))
    x, w = np.arange(len(labels)), 0.26
    for i, (k, c) in enumerate(zip(rows.columns, ["#9aa5b1", "#2a78d6", "#12110d"])):
        ax.bar(x + (i - 1) * w, rows[k], w, label=f"{k} P&L", color=c)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(x, labels)
    ax.set_ylabel("USD")
    ax.set_title("Long-call round trips at 1x: option vs share hedge")
    ax.legend(frameon=False, fontsize=8)
    return report.save(fig, folder / "long_split.png")


def holds(sets, folder):
    labels, years = [l for l in sets if l != "baseline"], np.arange(2014, 2025)
    fig, ax = plt.subplots(figsize=(7, 3))
    for i, l in enumerate(labels):
        ev = sets[l][1.0]["events"]
        held = ev[ev["event"] == "trend_hold"] if len(ev) else ev
        n = pd.to_datetime(held["date"]).dt.year.value_counts() if len(held) else pd.Series(dtype=int)
        ax.bar(years + (i - 1) * 0.26, [n.get(y, 0) for y in years], 0.26, label=l,
               color=report.color(i + 1, l))
    ax.set_xticks(years)
    ax.set_ylabel("hedges held")
    ax.set_title("Hedges the wider long-call band held back, by year (1x)")
    ax.legend(frameon=False, fontsize=8)
    return report.save(fig, folder / "trend_holds.png")


def extra(cfg, sets, folder):
    # long-side split and how often the band held
    return [long_split(sets, folder), holds(sets, folder)]


def build(cfg, holdout=False):
    sets = load_sets(cfg, holdout)
    folder = FIGS / "holdout" if holdout else FIGS
    tab = report.table(sets)
    folder.mkdir(parents=True, exist_ok=True)
    tab.to_csv(folder / "table.csv", index=False)
    paths = [report.cum_pnl(sets, folder / "cum_pnl.png")] if holdout else (
        report.standard(sets, folder) + extra(cfg, sets, folder))
    chk = checks(cfg, tab, holdout)
    chk.to_csv(folder / "pass_bar.csv", index=False)
    cols = ["label", "mult", "period", "pnl", "sharpe", "max_dd", "es_5", "trades",
            "win_rate", "gross", "option_fees", "hedge_fees", "hedge_orders"]
    print(tab[cols].round(2).to_string(index=False))
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
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
