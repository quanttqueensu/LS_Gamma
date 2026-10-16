import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-short-only-band10"  # matches configs/experiments/<NAME>.toml
REF = "2026-10-16-short-only/short_only"  # registered reference, not rerun
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
    base = report.baseline(config.load(), holdout)
    if holdout:
        p = cfg["pass"]["primary"]
        return {"baseline": base, p: report.runs(f"{NAME}/{p}", True)}
    return {"baseline": base, "short_only": report.runs(REF),
            **{v: report.runs(f"{NAME}/{v}") for v in cfg["variants"]}}


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, holdout=False):
    p, rows = cfg["pass"], []
    against = "baseline" if holdout else p.get("against", "baseline")
    for c in p["check"]:
        if holdout and c["period"] != "all":
            continue
        for m in MULTS:
            v = value(tab, p["primary"], m, c["period"], c["metric"])
            r = value(tab, against, m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def cut(cfg, sets):
    # 1x hedge-order cut, primary vs reference
    p = cfg["pass"]
    n, ref = len(sets[p["primary"]][1.0]["hedges"]), len(sets[p["against"]][1.0]["hedges"])
    return n, ref, 1 - n / ref


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if not holdout and p.get("hedge_cut", 0):
        n, ref, c = cut(cfg, sets)
        if c < p["hedge_cut"]:
            return f"INCONCLUSIVE (hedge orders {n} vs {ref}, cut {c:.0%} < {p['hedge_cut']:.0%})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def bridge(sets):
    # net = gross - commissions + unwind residual
    rows = []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            s, rt = report.stats(out), report.round_trips(out)
            rt_net = float(rt["pnl_net"].sum()) if len(rt) else 0.0
            rows.append({"label": label, "mult": mult, "net": s["pnl"], "gross": s["gross"],
                         "commissions": s["gross"] - rt_net, "residual": s["pnl"] - rt_net,
                         "all_fees": s["option_fees"] + s["hedge_fees"]})
    return pd.DataFrame(rows)


def matched(sets, a="short_only", b="band10", mult=1.0):
    # round trips with same entry, exit, reason
    ra, rb = report.round_trips(sets[a][mult]), report.round_trips(sets[b][mult])
    m = ra.merge(rb, on=["side", "entry_date"], suffixes=("_a", "_b"))
    m = m[(m["exit_date_a"] == m["exit_date_b"]) & (m["reason_a"] == m["reason_b"])]
    return {"mult": mult, "trips_ref": len(ra), "trips_band": len(rb), "matched": len(m),
            "gross_gain_matched": float((m["pnl_b"] - m["pnl_a"]).sum()),
            "net_gain_matched": float((m["pnl_net_b"] - m["pnl_net_a"]).sum())}


def hedge_counts(ax, sets, col, title, ylabel):
    labels, w = list(sets), 0.38
    xs = np.arange(len(labels))
    for j, mult in enumerate(MULTS):
        h = [sets[k][mult]["hedges"] for k in labels]
        ys = [len(x) if col == "orders" else float(x["commission"].sum()) for x in h]
        ax.bar(xs + (j - 0.5) * w, ys, w, color=[report.color(i, k) for i, k in enumerate(labels)],
               alpha=1.0 if mult == 1.0 else 0.55, label=f"{mult:g}x")
    ax.set_xticks(xs, labels)
    ax.set(title=title, ylabel=ylabel)
    ax.legend(fontsize=7, frameon=False, title="spreads (light = 2x)", title_fontsize=6.5)


def hedging(sets, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.9))
    hedge_counts(axes[0], sets, "orders", "Hedge orders, 2014-2024", "orders")
    hedge_counts(axes[1], sets, "fees", "Hedge commissions, 2014-2024", "USD")
    return report.save(fig, path)


def hedge_sizes(sets, path, mult=1.0):
    bins = np.arange(0, 104, 2)
    fig, ax = plt.subplots(figsize=(7, 2.9))
    for i, (label, by_mult) in enumerate(sets.items()):
        h = by_mult[mult]["hedges"]
        size = h["shares"].abs().clip(upper=bins[-1] - 1)
        ax.hist(size, bins, histtype="step", lw=1.2, color=report.color(i, label),
                label=f"{label} ({len(h)} orders)")
    ax.set(title=f"Shares per hedge order, {mult:g}x", ylabel="orders",
           xlabel="|shares| per order (last bin 100+)")
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def pnl_bridge(br, path, labels=("short_only", "band10")):
    parts = [("gross", "gross round-trip P&L", "tab:blue"),
             ("commissions", "commissions (minus)", "tab:orange"),
             ("residual", "unattributed unwind residual", "tab:purple")]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    for ax, mult in zip(axes, MULTS):
        d = br[(br["mult"] == mult) & br["label"].isin(labels)].set_index("label").loc[list(labels)]
        xs = np.arange(len(d))
        for j, (col, name, c) in enumerate(parts):
            ys = -d[col] if col == "commissions" else d[col]
            ax.bar(xs + (j - 1) * 0.25, ys, 0.25, color=c, label=name)
        ax.plot(xs, d["net"], "kD", ms=5, label="net P&L")
        ax.axhline(0, color="k", lw=0.6)
        ax.set_xticks(xs, d.index)
        ax.set(title=f"P&L bridge, {mult:g}x", ylabel="USD, 1 contract")
    axes[0].legend(fontsize=6.5, frameon=False, loc="lower left")
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # hedge orders, order sizes, P&L bridge
    br = bridge(sets)
    br.to_csv(folder / "pnl_bridge.csv", index=False)
    return [hedging(sets, folder / "hedging.png"), hedge_sizes(sets, folder / "hedge_sizes.png"),
            pnl_bridge(br, folder / "pnl_bridge.png")]


def diagnostics(cfg, sets):
    pd.set_option("display.width", 200)
    print("\nP&L bridge\n" + bridge(sets).round(2).to_string(index=False))
    print("\nmatched round trips (short_only vs band10)")
    print(pd.DataFrame([matched(sets, mult=m) for m in MULTS]).round(2).to_string(index=False))
    n, ref, c = cut(cfg, sets)
    print(f"\nhedge orders at 1x: band10 {n} vs short_only {ref} (cut {c:.1%})")


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
    if not holdout:
        diagnostics(cfg, sets)
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk, holdout)}")
    print(f"trials: {report.trials(NAME)} (+ reference {report.trials(REF)} reused, "
          f"+ baseline {report.trials('baseline')})")
    print("figures:", *[Path(p).name for p in paths])


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
