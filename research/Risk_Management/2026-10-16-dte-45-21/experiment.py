import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, metrics, report, run

NAME = "2026-10-16-dte-45-21"  # matches configs/experiments/<NAME>.toml
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
    ref = report.baseline(config.load(), holdout)
    if holdout:
        p = cfg["pass"]["primary"]
        return {"baseline": ref, p: report.runs(f"{NAME}/{p}", True)}
    return {"baseline": ref, "short_only": report.runs(REF),
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


def events(out, reason):
    if reason == "round_trips":
        return len(report.round_trips(out))
    t = out["trades"]
    return int(((t["action"] == "close") & (t["reason"] == reason)).sum()) if len(t) else 0


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if p.get("min_events", 0) and not holdout:
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def holds(out):
    rt = report.round_trips(out)
    return (pd.to_datetime(rt["exit_date"]) - pd.to_datetime(rt["entry_date"])).dt.days


def to_expiry(df):
    return (pd.to_datetime(df["expiry"]) - pd.to_datetime(df["date"])).dt.days


def dtes(out):
    o, c = metrics.pairs(out["trades"])
    return to_expiry(o), to_expiry(c)


def boxes(ax, data, labels, title):
    ax.boxplot(data, tick_labels=labels, showfliers=False, whis=(5, 95))
    ax.set(title=title, ylabel="days")
    ax.tick_params(axis="x", labelsize=7)


def hold_dist(cfg, sets, path):
    labels = list(sets)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    boxes(ax, [holds(sets[k][1.0]) for k in labels], labels,
          "Holding period per round trip (calendar days, 1x)")
    return report.save(fig, path)


def dte_dist(cfg, sets, path):
    labels = list(sets)
    pairs = [dtes(sets[k][1.0]) for k in labels]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8), sharey=True)
    boxes(axes[0], [p[0] for p in pairs], labels, "DTE at entry (1x)")
    boxes(axes[1], [p[1] for p in pairs], labels, "DTE at exit (1x)")
    return report.save(fig, path)


def costs(cfg, sets, path):
    labels = list(sets)
    trips = [len(report.round_trips(sets[k][1.0])) for k in labels]
    s1 = [report.stats(sets[k][1.0]) for k in labels]
    spread = [a["pnl"] - report.stats(sets[k][2.0])["pnl"] for a, k in zip(s1, labels)]
    fees = [a["option_fees"] + a["hedge_fees"] for a in s1]
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8))
    axes[0].bar(labels, trips, color=[report.color(i, k) for i, k in enumerate(labels)])
    axes[0].set(title="Round trips, 2014-2024", ylabel="count")
    axes[1].bar(labels, spread, color="tab:blue", label="spreads (1x)")
    axes[1].bar(labels, fees, bottom=spread, color="tab:orange", label="commissions")
    axes[1].set(title="Trading costs at 1x", ylabel="USD",
                ylim=(0, max(map(sum, zip(spread, fees))) * 1.3))
    axes[1].legend(fontsize=7, frameon=False, ncol=2, loc="upper left")
    for ax in axes:
        ax.tick_params(axis="x", labelsize=7)
    return report.save(fig, path)


def mechanics(sets):
    # aggregates for the report text
    for k, by_mult in sets.items():
        out = by_mult[1.0]
        rt, ev = report.round_trips(out), out["events"]
        entry, exit_ = dtes(out)
        n = ev["event"].value_counts().to_dict() if len(ev) else {}
        print(f"{k}: trips {len(rt)}  reasons {rt['reason'].value_counts().to_dict()}  "
              f"hold med {holds(out).median():.0f}  entry dte med {entry.median():.0f}  "
              f"exit dte med {exit_.median():.0f}  no_mark {n.get('no_mark', 0)}  "
              f"no_entry {n.get('no_entry', 0)}  last trade {out['trades']['date'].max()}")


def extra(cfg, sets, folder):
    # holding, DTE and costs: the mechanism
    mechanics(sets)
    return [hold_dist(cfg, sets, folder / "holding.png"),
            dte_dist(cfg, sets, folder / "dte.png"),
            costs(cfg, sets, folder / "costs.png")]


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
    print(f"\nverdict: {verdict(cfg, sets, chk, holdout)}")
    print(f"trials: {report.trials(NAME)} (+ baseline {report.trials('baseline')}; "
          f"reference {REF} reused, {report.trials(REF)} trials, not rerun)")
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
