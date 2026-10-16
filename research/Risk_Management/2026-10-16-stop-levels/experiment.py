import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-stop-levels"
FIGS = Path(__file__).resolve().parent / "figures"
MULTS = (1.0, 2.0)
HALVES = ("2014-2019", "2020-2024")
YEARS = range(2014, 2025)


def sets(cfg):
    out = {"baseline": report.runs("baseline")}
    return {**out, **{v: report.runs(f"{NAME}/{v}") for v in cfg["variants"]}}


def get(tab, label, mult, period, col):
    r = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(r[col].iloc[0])


def check(rows, hyp, label, mult, name, value, bar, ok):
    rows.append({"hypothesis": hyp, "variant": label, "mult": mult, "check": name,
                 "value": round(value, 1), "bar": round(bar, 1), "ok": bool(ok)})


def h1(tab, p, rows):
    v = p["h1_variant"]
    for m in MULTS:
        es_b = abs(get(tab, "baseline", m, "all", "es_5"))
        es_v = abs(get(tab, v, m, "all", "es_5"))
        check(rows, "H1", v, m, "|ES 5%| all <= ratio x base", es_v, p["h1_es_ratio"] * es_b,
              es_v <= p["h1_es_ratio"] * es_b)
        for half in HALVES:
            b, x = abs(get(tab, "baseline", m, half, "es_5")), abs(get(tab, v, m, half, "es_5"))
            check(rows, "H1", v, m, f"|ES 5%| {half} < base", x, b, x < b)
        pnl_b, pnl_v = get(tab, "baseline", m, "all", "pnl"), get(tab, v, m, "all", "pnl")
        check(rows, "H1", v, m, "net P&L all >= base - give", pnl_v, pnl_b - p["h1_pnl_give"],
              pnl_v >= pnl_b - p["h1_pnl_give"])


def h2(tab, p, rows):
    v = p["h2_variant"]
    for m in MULTS:
        for period in ("all",) + HALVES:
            b, x = get(tab, "baseline", m, period, "pnl"), get(tab, v, m, period, "pnl")
            check(rows, "H2", v, m, f"net P&L {period} > base", x, b, x > b)
        es_b = abs(get(tab, "baseline", m, "all", "es_5"))
        es_v = abs(get(tab, v, m, "all", "es_5"))
        check(rows, "H2", v, m, "|ES 5%| all <= ratio x base", es_v, p["h2_es_ratio"] * es_b,
              es_v <= p["h2_es_ratio"] * es_b)


def evaluate(tab, p):
    rows = []
    h1(tab, p, rows)
    h2(tab, p, rows)
    return pd.DataFrame(rows)


def trips(sets):
    rows = []
    for label, by_mult in sets.items():
        for mult, out in by_mult.items():
            rt = report.round_trips(out)
            if len(rt):
                year = pd.to_datetime(rt["exit_date"]).dt.year
                rows.append(rt.assign(label=label, mult=mult, year=year,
                                      ratio=rt["pnl_net"] / rt["premium"]))
    return pd.concat(rows, ignore_index=True)


def exits_per_year(rt, labels, path):
    fig, axes = plt.subplots(2, 2, figsize=(7.5, 4.6), sharex=True, sharey="row")
    n = len(labels)
    for row, reason in zip(axes, ("stop", "profit")):
        for ax, mult in zip(row, MULTS):
            for i, label in enumerate(labels):
                r = rt[(rt["label"] == label) & (rt["mult"] == mult) & (rt["reason"] == reason)]
                y = r.groupby("year").size().reindex(YEARS, fill_value=0)
                ax.bar(y.index + (i - (n - 1) / 2) * 0.8 / n, y.values, 0.8 / n,
                       color=report.color(i, label), label=label)
            ax.set(title=f"{reason} exits per year, {mult:g}x", ylabel="round trips")
            ax.set_ylim(bottom=0)
            ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    axes[0][0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def pnl_premium(rt, labels, path):
    fig, axes = plt.subplots(2, 2, figsize=(7.5, 5.2), sharey="row")
    for row, side in zip(axes, ("short", "long")):
        for ax, mult in zip(row, MULTS):
            data, names = [], []
            for label in labels:
                r = rt[(rt["label"] == label) & (rt["mult"] == mult) & (rt["side"] == side)]
                data.append(r["ratio"].dropna().to_numpy())
                names.append(f"{label}\nn={len(r)}")
            # whiskers 5-95%, no single-trade points
            b = ax.boxplot(data, whis=(5, 95), showfliers=False, showmeans=True,
                           patch_artist=True, medianprops={"color": "k"},
                           meanprops={"marker": "D", "markerfacecolor": "w",
                                      "markeredgecolor": "k", "markersize": 4})
            for i, (box, label) in enumerate(zip(b["boxes"], labels)):
                box.set(facecolor=report.color(i, label), alpha=0.6)
            ax.set_xticks(range(1, len(labels) + 1), names, fontsize=7)
            ax.axhline(0, color="k", lw=0.6)
            ax.set(title=f"{side} round trips, {mult:g}x", ylabel="net P&L / premium")
    fig.suptitle("Box: quartiles, median line, mean diamond; whiskers 5th-95th pct",
                 fontsize=8)
    return report.save(fig, path)


def build(cfg):
    s = sets(cfg)
    labels = list(s)
    tab = report.table(s)
    rt = trips(s)
    report.standard(s, FIGS)
    exits_per_year(rt, labels, FIGS / "exits_per_year.png")
    pnl_premium(rt, labels, FIGS / "pnl_premium.png")
    counts = rt.groupby(["label", "mult", "side", "reason"]).size().unstack(fill_value=0)
    bars = evaluate(tab, cfg["pass"])
    tab.to_csv(FIGS / "results.csv", index=False)
    bars.to_csv(FIGS / "pass_bar.csv", index=False)
    return tab, counts, bars


def verdict(bars):
    ok = bars.groupby("hypothesis")["ok"].all()
    return ", ".join(f"{h} {'passed' if v else 'failed'}" for h, v in ok.items())


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.add_argument("--report-only", action="store_true", help="rebuild from registered runs")
    a = p.parse_args()
    cfg = config.load(NAME)
    if not a.report_only:
        for v, rows in run.variants(NAME, cfg, cfg["variants"]).items():
            print(f"\n{v}\n{run.table(rows)}")
    tab, counts, bars = build(cfg)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(f"\nresults (all periods, 1x and 2x)\n{tab.round(3).to_string(index=False)}")
        print(f"\nexits by side and reason\n{counts.to_string()}")
        print(f"\npass bar checks\n{bars.to_string(index=False)}")
    print(f"\nverdict: {verdict(bars)}")
    print(f"trials: {report.trials(NAME)} (plus the baseline's 2); figures in {FIGS}")


if __name__ == "__main__":
    main()
