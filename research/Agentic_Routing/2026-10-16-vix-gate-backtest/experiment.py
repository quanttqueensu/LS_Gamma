import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, engine, report, run

NAME = "2026-10-16-vix-gate-backtest"  # matches configs/experiments/<NAME>.toml
REF = "2026-10-16-short-only/short_only"  # registered reference, not rerun
FIGS = Path(__file__).resolve().parent / "figures"
MULTS = (1.0, 2.0)
RULES = {
    "higher": lambda v, r, x: v > r,
    "less_severe": lambda v, r, x: abs(v) < abs(r),
    "abs_within": lambda v, r, x: abs(v) <= x * abs(r),
    "not_below": lambda v, r, x: v >= r - x,
}
HOLDOUT = [{"metric": "pnl", "period": "all", "rule": "higher"},
           {"metric": "es_5", "period": "all", "rule": "abs_within", "value": 1.10}]


def load_sets(cfg, holdout=False):
    # baseline first so it is drawn grey
    base = {"baseline": report.baseline(config.load(), holdout)}
    if holdout:
        p = cfg["pass"]["primary"]
        return {**base, p: report.runs(f"{NAME}/{p}", True)}
    return {**base, "short_only": report.runs(REF),
            **{v: report.runs(f"{NAME}/{v}") for v in cfg["variants"]}}


def value(tab, label, mult, period, metric):
    row = tab[(tab["label"] == label) & (tab["mult"] == mult) & (tab["period"] == period)]
    return float(row[metric].iloc[0])


def checks(cfg, tab, holdout=False):
    p, rows = cfg["pass"], []
    against = "baseline" if holdout else p.get("against", "baseline")
    for c in HOLDOUT if holdout else p["check"]:
        for m in MULTS:
            v = value(tab, p["primary"], m, c["period"], c["metric"])
            r = value(tab, against, m, c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def gate_days(out, event="gate"):
    e = out["events"]
    return pd.to_datetime(e.loc[e["event"] == event, "date"].unique()) if len(e) else (
        pd.DatetimeIndex([]))


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if p.get("min_events", 0) and not holdout:
        n = len(gate_days(sets[p.get("event_label", p["primary"])][1.0], p["event"]))
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} gated days < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def ratio(cfg):
    # yesterday's close ratio, as the gate sees it
    f = pd.read_parquet(engine.snapshots(cfg) / "features.parquet")
    return f["vix_vix3m"].shift(1)


def gated_labels(cfg, sets):
    return [k for k in sets if k in cfg["variants"]]


def per_year(cfg, sets, path):
    labels = gated_labels(cfg, sets)
    years = range(2014, 2025)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    w = 0.8 / len(labels)
    for i, k in enumerate(labels):
        n = pd.Series(gate_days(sets[k][1.0]).year).value_counts()
        ax.bar([y + (i - (len(labels) - 1) / 2) * w for y in years],
               [int(n.get(y, 0)) for y in years], width=w, label=k,
               color=report.color(i + 2, k))
    ax.set(title="Days the gate blocked a short entry (1x)", ylabel="days", xticks=list(years))
    ax.tick_params(axis="x", labelsize=7)
    ax.legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def ratio_chart(cfg, sets, path):
    prev = ratio(cfg).loc["2014-06-02":"2024-12-31"]
    fig, ax = plt.subplots(figsize=(7, 3.0))
    ax.plot(prev.index, prev.values, color="0.55", lw=0.6, label="VIX/VIX3M (prior close)")
    for i, k in enumerate(gated_labels(cfg, sets)):
        g = gate_days(sets[k][1.0])
        ax.scatter(g, prev.reindex(g).values, s=6, color=report.color(i + 2, k),
                   label=f"{k} blocked days", zorder=3)
        ax.axhline(sets[k][1.0]["cfg"]["backtest"]["short_gate"], color=report.color(i + 2, k),
                   lw=0.8, ls="--")
    ax.set(title="VIX/VIX3M the gate reads, with blocked days (1x)", ylabel="ratio")
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    return report.save(fig, path)


def ref_split(cfg, sets, path):
    # reference trades whose entry day would gate
    prev = ratio(cfg)
    gates = [(k, sets[k][1.0]["cfg"]["backtest"]["short_gate"]) for k in gated_labels(cfg, sets)]
    fig, axes = plt.subplots(1, len(gates), figsize=(7.5, 2.9), sharey=True, squeeze=False)
    for ax, (k, g) in zip(axes[0], gates):
        for j, m in enumerate(MULTS):
            rt = report.round_trips(sets["short_only"][m])
            hit = prev.reindex(pd.to_datetime(rt["entry_date"])).values >= g
            sums = [rt.loc[hit, "pnl_net"].sum(), rt.loc[~hit, "pnl_net"].sum()]
            bars = ax.bar([x + (j - 0.5) * 0.38 for x in (0, 1)], sums, width=0.38,
                          color="tab:blue" if m == 1.0 else "tab:orange", label=f"{m:g}x")
            if j == 0:
                ax.bar_label(bars, labels=[f"n={int(hit.sum())}", f"n={int((~hit).sum())}"],
                             fontsize=7, padding=2)
        ax.axhline(0, color="0.3", lw=0.6)
        ax.set(title=f"short_only trades, gate {g:g}", xticks=[0, 1],
               xticklabels=["would gate", "would not"])
    axes[0][0].set(ylabel="net P&L (USD)")
    axes[0][0].legend(fontsize=7, frameon=False)
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # gate activity and what it removes
    return [per_year(cfg, sets, folder / "gate_per_year.png"),
            ratio_chart(cfg, sets, folder / "vix_ratio.png"),
            ref_split(cfg, sets, folder / "ref_split.png")]


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
        for k in gated_labels(cfg, sets):
            print(f"{k}: gate blocked shorts on {len(gate_days(sets[k][1.0]))} days (1x), "
                  f"{len(gate_days(sets[k][2.0]))} days (2x)")
    print("\npass bar" + (" (hold-out)" if holdout else ""))
    print(chk.round(2).to_string(index=False))
    print(f"\nverdict: {verdict(cfg, sets, chk, holdout)}")
    print(f"trials: {report.trials(NAME)} (+ reference reused from 2026-10-16-short-only, "
          f"{report.trials(REF)} trials, not rerun; + baseline {report.trials('baseline')})")
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
