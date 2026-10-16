import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-hedge-band"  # matches configs/experiments/<NAME>.toml
PRIMARY = "band10"  # only variant the pass bar uses
ES_LIMIT = 1.10  # band10 |ES| over baseline |ES|
MULTS = (1.0, 2.0)
PERIODS = ("all", "2014-2019", "2020-2024")
FIGS = Path(__file__).resolve().parent / "figures"


def baseline():
    # trial 1: first baseline run per mult
    reg = report.registry()
    first = reg[reg["experiment"] == "baseline"].groupby("spread_mult").head(1)
    return {float(r.spread_mult): report.load(r.run) for r in first.itertuples()}


def bands(cfg):
    out = {"baseline": cfg["hedge"]["min_shares"]}
    return {**out, **{v: o["hedge"]["min_shares"] for v, o in cfg["variants"].items()}}


def load_sets(cfg):
    return {"baseline": baseline(), **{v: report.runs(f"{NAME}/{v}") for v in cfg["variants"]}}


def hedge_stats(sets, band):
    rows = []
    for label, by_mult in sets.items():
        for mult, out in sorted(by_mult.items()):
            h, e = out["hedges"], out["equity"]
            size = h["shares"].abs() if len(h) else pd.Series(dtype=float)
            flat = e[e["option"] == 0]
            rows.append({"label": label, "band": band[label], "mult": mult, "orders": len(h),
                         "fees": float(h["commission"].sum()) if len(h) else 0.0,
                         "median_size": size.median(), "mean_size": size.mean(),
                         "flat_abs_shares": float(flat["shares"].abs().mean())})
    return pd.DataFrame(rows)


def verdict(tab):
    rows = []
    for mult in MULTS:
        t = tab[tab["mult"] == mult].set_index(["label", "period"])
        for period in PERIODS:
            b, v = t.loc[("baseline", period), "pnl"], t.loc[(PRIMARY, period), "pnl"]
            rows.append({"bar": f"1. net P&L > baseline ({period})", "mult": mult,
                         PRIMARY: v, "baseline": b, "pass": bool(v > b)})
        b, v = t.loc[("baseline", "all"), "es_5"], t.loc[(PRIMARY, "all"), "es_5"]
        rows.append({"bar": f"2. |ES 5%| <= {ES_LIMIT:.2f}x baseline (all)", "mult": mult,
                     PRIMARY: v, "baseline": b, "pass": bool(abs(v) <= ES_LIMIT * abs(b))})
    return pd.DataFrame(rows)


def ticks(ax, band):
    xs = sorted(set(band.values()))
    ax.set_xticks(xs, [f"{x}\n(baseline)" if x == band["baseline"] else str(x) for x in xs])
    ax.set_xlabel("hedge band, min_shares")


def hedge_costs(hs, band, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3))
    for ax, col, title in zip(axes, ("orders", "fees"), ("Hedge orders", "Hedge commissions")):
        for mult in MULTS:
            d = hs[hs["mult"] == mult].sort_values("band")
            ax.plot(d["band"], d[col], report.STYLE[mult], marker="o",
                    color="tab:blue" if mult == 1.0 else "tab:orange", label=f"{mult:g}x spreads")
        ax.set(title=title, ylabel="count" if col == "orders" else "USD")
        ax.set_ylim(bottom=0)
        ticks(ax, band)
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def hedge_sizes(sets, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    bins = np.arange(0, 104, 2)
    for ax, mult in zip(axes, MULTS):
        for i, (label, by_mult) in enumerate(sets.items()):
            h = by_mult[mult]["hedges"] if mult in by_mult else pd.DataFrame()
            if len(h):
                size = h["shares"].abs().clip(upper=bins[-1] - 1)
                ax.hist(size, bins, histtype="step", lw=1.2, color=report.color(i, label),
                        label=f"{label} ({len(h)})")
        ax.set(title=f"Shares per hedge order, {mult:g}x", ylabel="orders",
               xlabel="|shares| per order (last bin 100+)")
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def pnl_vs_band(tab, band, path):
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 3), sharey=True)
    tab = tab.assign(band=tab["label"].map(band))
    for ax, mult in zip(axes, MULTS):
        for period, c in zip(PERIODS, ("k", "tab:blue", "tab:green")):
            d = tab[(tab["mult"] == mult) & (tab["period"] == period)].sort_values("band")
            ax.plot(d["band"], d["pnl"], marker="o", color=c, lw=1.6 if period == "all" else 1,
                    label=period)
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L by hedge band, {mult:g}x", ylabel="USD, 1 contract")
        ticks(ax, band)
    axes[0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def build(cfg):
    band, sets = bands(cfg), load_sets(cfg)
    tab, hs = report.table(sets), hedge_stats(sets, band)
    v = verdict(tab)
    FIGS.mkdir(parents=True, exist_ok=True)
    tab.to_csv(FIGS / "table.csv", index=False)
    hs.to_csv(FIGS / "hedge_stats.csv", index=False)
    v.to_csv(FIGS / "pass_bar.csv", index=False)
    files = report.standard(sets, FIGS)
    files += [hedge_costs(hs, band, FIGS / "hedge_costs.png"),
              hedge_sizes(sets, FIGS / "hedge_sizes.png"),
              pnl_vs_band(tab, band, FIGS / "pnl_vs_band.png")]
    pd.set_option("display.width", 200)
    for mult in MULTS:
        t = tab[tab["mult"] == mult].round(3)
        print(f"\nresults, {mult:g}x spreads\n" + t.to_string(index=False))
    print("\nhedging\n" + hs.round(2).to_string(index=False))
    print("\npass bar (band10 vs baseline trial 1)\n" + v.round(2).to_string(index=False))
    print(f"\nverdict: {'PASSED' if v['pass'].all() else 'FAILED'}")
    print(f"trials: {report.trials(NAME)} (+2 baseline)")
    print("figures: " + ", ".join(Path(f).name for f in files))


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    a = p.parse_args()
    cfg = config.load(NAME)
    if not a.report_only:
        if report.trials(NAME):
            raise SystemExit(f"{NAME} already has trials; use --report-only")
        for label, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{label}\n{run.table(rows)}")
    build(cfg)


if __name__ == "__main__":
    main()
