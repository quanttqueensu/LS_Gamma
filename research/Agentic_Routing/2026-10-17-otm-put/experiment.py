import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from lsgamma.backtest import config, report, run

NAME = "2026-10-17-otm-put"  # matches configs/experiments/<NAME>.toml
FIGS = Path(__file__).resolve().parent / "figures"
REF = "2026-10-16-short-only-band10/band10"  # reused, not rerun
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
    ours = {v: report.runs(f"{NAME}/{v}", holdout) for v in labels}
    return {"baseline": ref, **({} if holdout else {"band10": report.runs(REF)}), **ours}


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
            r = value(tab, "baseline" if holdout else p.get("against", "baseline"), m,
                      c["period"], c["metric"])
            ok = RULES[c["rule"]](v, r, c.get("value", 0.0))
            rows.append({"check": f"{c['metric']} {c['rule']} {c.get('value', '')} ({c['period']})",
                         "mult": m, "variant": v, "against": r, "pass": ok})
    return pd.DataFrame(rows)


def events(out, reason):
    t = out["trades"]
    if reason == "round_trip":
        return len(report.round_trips(out))
    return int(((t["action"] == "close") & (t["reason"] == reason)).sum()) if len(t) else 0


def verdict(cfg, sets, chk, holdout=False):
    p = cfg["pass"]
    if p.get("min_events", 0) and not holdout:
        n = events(sets[p.get("event_label", p["primary"])][1.0], p["event"])
        if n < p["min_events"]:
            return f"INCONCLUSIVE ({n} {p['event']} exits < {p['min_events']})"
    return "PASSED" if chk["pass"].all() else "FAILED"


def books(sets):
    return [k for k in sets if k != "baseline"]


def premium(sets, path):
    labels = books(sets)
    fig, ax = plt.subplots(figsize=(7, 2.8))
    ax.boxplot([report.round_trips(sets[k][1.0])["premium"] for k in labels], tick_labels=labels,
               showfliers=False, whis=(5, 95))
    ax.set(title="Credit collected per round trip (USD, 1 contract, 1x)", ylabel="USD")
    return report.save(fig, path)


def exits(sets, path):
    labels = books(sets)
    rows = {k: report.round_trips(sets[k][1.0])["reason"].value_counts() for k in labels}
    df = pd.DataFrame(rows).fillna(0).T
    fig, ax = plt.subplots(figsize=(7, 2.8))
    df.plot.bar(ax=ax, stacked=True, rot=0)
    ax.set(title="Round trips by exit reason (1x)", ylabel="count", ylim=(0, df.sum(axis=1).max() * 1.3))
    ax.legend(fontsize=7, frameon=False, ncol=4, loc="upper center")
    return report.save(fig, path)


def per_trade(sets, path):
    labels = books(sets)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, 2.8))
    for ax, m in zip(axes, MULTS):
        net = [report.stats(sets[k][m])["pnl"] / max(len(report.round_trips(sets[k][m])), 1)
               for k in labels]
        ax.bar(labels, net, color=[report.color(i + 1, k) for i, k in enumerate(labels)])
        ax.axhline(0, color="k", lw=0.6)
        ax.set(title=f"Net P&L per round trip, {m:g}x", ylabel="USD")
    return report.save(fig, path)


def extra(cfg, sets, folder):
    # premium, exits and per-trade edge
    return [premium(sets, folder / "premium.png"), exits(sets, folder / "exits.png"),
            per_trade(sets, folder / "per_trade.png")]


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
          f"reference {REF} reused, 2 trials, not rerun)")
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
