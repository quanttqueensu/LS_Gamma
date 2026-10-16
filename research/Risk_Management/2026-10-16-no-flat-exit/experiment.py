import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-16-no-flat-exit"  # matches configs/experiments/<NAME>.toml
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


def events(out, reason):
    t = out["trades"]
    return int(((t["action"] == "close") & (t["reason"] == reason)).sum()) if len(t) else 0


def verdict(cfg, sets, chk):
    p = cfg["pass"]
    if p.get("min_events", 0):
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} exits < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def holds(out):
    rt = report.round_trips(out)
    return (pd.to_datetime(rt["exit_date"]) - pd.to_datetime(rt["entry_date"])).dt.days


def turnover(cfg, sets, path):
    labels = list(sets)
    trips = [len(report.round_trips(sets[k][1.0])) for k in labels]
    spread = [report.stats(sets[k][1.0])["pnl"] - report.stats(sets[k][2.0])["pnl"] for k in labels]
    fees = [report.stats(sets[k][1.0])["option_fees"] + report.stats(sets[k][1.0])["hedge_fees"]
            for k in labels]
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


def hold_dist(cfg, sets, path):
    labels = list(sets)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.boxplot([holds(sets[k][1.0]) for k in labels], tick_labels=labels, showfliers=False,
               whis=(5, 95))
    ax.set(title="Holding period per round trip (calendar days, 1x)", ylabel="days")
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # turnover and holding: the mechanism
    return [turnover(cfg, sets, folder / "turnover.png"),
            hold_dist(cfg, sets, folder / "holding.png")]


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
